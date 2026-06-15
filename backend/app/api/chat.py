"""
对话 API 路由（RAG 增强版）
============
提供基于知识库的智能问答功能：
1. POST /api/chat/ask - RAG 智能问答（支持流式输出）
2. GET /api/chat/sessions - 获取用户会话列表
3. POST /api/chat/sessions - 创建新会话
4. GET /api/chat/sessions/{id}/messages - 获取会话消息
5. POST /api/chat/messages/{id}/feedback - 提交消息反馈
"""

import json
import logging
import re
import sys
import traceback
from typing import Generator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, date
from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models import User, UserRole, ChatSession, Message, Document, Announcement, QuestionStat, get_beijing_time
from app.schemas import MessageCreate, MessageResponse, SessionCreate, SessionResponse, ChatAskRequest, ChatAskResponse, FeedbackRequest, FeedbackResponse
from app.services.qa_service import QAService
from app.services.answer_verifier import answer_verifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["对话"])
qa_service = QAService()


def reset_daily_count_if_needed(user: User, db: Session):
    """重置每日计数（如果跨天了）"""
    today = date.today()
    if user.last_reset_date is None or user.last_reset_date != today:
        user.questions_today = 0
        user.uploads_today = 0
        user.last_reset_date = today
        db.commit()
        db.refresh(user)


def record_question_stat(content: str, db: Session):
    """
    记录问题统计（持久化，不随删除减少）
    注意：此函数不提交事务，由调用方统一提交
    """
    content = content.strip()
    if not content:
        return
    
    stat = db.query(QuestionStat).filter(QuestionStat.content == content).first()
    if stat:
        stat.count += 1
        stat.updated_at = get_beijing_time()
    else:
        stat = QuestionStat(content=content, count=1)
        db.add(stat)


def get_chat_history(session_id: int, db: Session, max_tokens: int = 3000) -> list:
    """
    获取对话历史（智能摘要感知）
    - 如果存在摘要消息，只加载摘要 + 之后的新消息
    - 如果无摘要，按 token 预算加载最多 100 条
    
    Args:
        session_id: 会话ID
        db: 数据库会话
        max_tokens: 最大 token 预算
        
    Returns:
        对话历史列表
    """
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).limit(200).all()
    
    summary_index = None
    for i, msg in enumerate(messages):
        if msg.role == "summary":
            summary_index = i
    
    if summary_index is not None:
        start = summary_index
        logger.info(f"对话历史: 从摘要消息(#{messages[summary_index].id})恢复，跳过 {summary_index} 条旧消息")
    else:
        start = max(0, len(messages) - 200)
    
    from app.services.summary_service import SummaryService
    token_count = 0
    result = []
    for msg in messages[start:]:
        msg_tokens = SummaryService.estimate_tokens(msg.content)
        if token_count + msg_tokens <= max_tokens:
            result.append({"role": msg.role, "content": msg.content})
            token_count += msg_tokens
        else:
            break
    
    return result


@router.post("/ask", response_model=ChatAskResponse)
def ask_question(
    request: ChatAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RAG 智能问答
    
    基于校园知识库回答用户问题，支持：
    - 向量检索相关文档
    - 多轮对话上下文
    - 流式输出（可选）
    """
    # 输入验证
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能为空")
    if len(request.content) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能超过2000字")
    # 检查用户状态
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    
    if current_user.ban_until and current_user.ban_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户已被封禁至 {current_user.ban_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    # 管理员无提问限制
    if current_user.role != UserRole.ADMIN:
        # 检查提问次数
        reset_daily_count_if_needed(current_user, db)
        
        if current_user.max_questions_per_day == 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您的提问权限已被限制，无法提问")
        
        if current_user.questions_today >= current_user.max_questions_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日提问次数已达上限 ({current_user.max_questions_per_day}次)，请明天再试"
            )
    
    # 创建或获取会话
    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == request.session_id,
            ChatSession.user_id == current_user.id
        ).first()
    
    if not session:
        session = ChatSession(
            user_id=current_user.id,
            title=request.content[:50] if len(request.content) > 50 else request.content,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # 保存用户消息
    user_message = Message(
        session_id=session.id,
        role="user",
        content=request.content,
    )
    db.add(user_message)
    db.commit()
    
    # 获取对话历史
    chat_history = get_chat_history(session.id, db)
    
    # 调用 RAG 问答
    result = qa_service.ask(
        question=request.content,
        chat_history=chat_history,
        top_k=request.top_k,
        db=db,
        user_role=current_user.role.value,
    )
    
    # 保存 AI 回答
    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        sources=json.dumps(result["sources"], ensure_ascii=False),
        confidence=result.get("confidence"),
        features=json.dumps(result.get("features", {}), ensure_ascii=False),
        token_usage=json.dumps(result.get("token_usage", {}), ensure_ascii=False),
    )
    db.add(assistant_message)
    db.commit()

    # 如果生成了摘要，保存到数据库
    if result.get("summary_text"):
        summary_msg = Message(
            session_id=session.id,
            role="summary",
            content=result["summary_text"],
        )
        db.add(summary_msg)
        db.commit()
        logger.info(f"对话摘要已保存到 DB: {result['summary_text'][:50]}...")
    
    # 增加今日提问计数（仅非管理员，用于每日限制）
    if current_user.role != UserRole.ADMIN:
        current_user.questions_today += 1
    
    # 记录问题统计（持久化）
    record_question_stat(request.content, db)
    
    db.commit()
    db.refresh(assistant_message)
    
    return ChatAskResponse(
        answer=result["answer"],
        sources=result["sources"],
        context_count=result["context_count"],
        session_id=session.id,
        message_id=assistant_message.id,
        confidence=result.get("confidence"),
        features=result.get("features"),
    )


@router.post("/ask/stream")
def ask_question_stream(
    request: ChatAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RAG 智能问答（流式输出）
    
    逐步返回生成的文本，提升用户体验
    """
    # 输入验证
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能为空")
    if len(request.content) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题内容不能超过2000字")
    # 检查用户状态
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    
    if current_user.ban_until and current_user.ban_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户已被封禁至 {current_user.ban_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    # 管理员无提问限制
    if current_user.role != UserRole.ADMIN:
        # 检查提问次数
        reset_daily_count_if_needed(current_user, db)
        
        if current_user.max_questions_per_day == 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您的提问权限已被限制，无法提问")
        
        if current_user.questions_today >= current_user.max_questions_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日提问次数已达上限 ({current_user.max_questions_per_day}次)，请明天再试"
            )
    
    # 保存用户 ID 到局部变量，避免在生成器中访问 Depends 注入的变量
    user_id = current_user.id
    user_role = current_user.role.value
    
    # 创建或获取会话
    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == request.session_id,
            ChatSession.user_id == user_id
        ).first()
    
    if not session:
        session = ChatSession(
            user_id=user_id,
            title=request.content[:50] if len(request.content) > 50 else request.content,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # 保存用户消息
    user_message = Message(
        session_id=session.id,
        role="user",
        content=request.content,
    )
    db.add(user_message)
    db.commit()
    
    # 获取对话历史
    chat_history = get_chat_history(session.id, db)

    def generate() -> Generator:
        """流式生成器（委托 qa_service.ask_stream）"""
        print(f"[DIAG] generate() 开始执行，user_id={user_id}, user_role={user_role}", file=sys.stderr, flush=True)
        gen_db = SessionLocal()
        
        try:
            print(f"[DIAG] 正在查询会话 id={session.id}", file=sys.stderr, flush=True)
            gen_session = gen_db.query(ChatSession).filter(ChatSession.id == session.id).first()
            if not gen_session:
                print("[DIAG] 无法在 gen_db 中找到会话", file=sys.stderr, flush=True)
                yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在，请刷新页面重试'}, ensure_ascii=False)}\n\n"
                return

            print(f"[DIAG] 会话找到：gen_session.id={gen_session.id}", file=sys.stderr, flush=True)

            chat_history_inner = get_chat_history(gen_session.id, gen_db)

            # 委托 qa_service.ask_stream() 处理核心 RAG pipeline
            done_data = None
            for event in qa_service.ask_stream(
                question=request.content,
                chat_history=chat_history_inner,
                top_k=request.top_k,
                db=gen_db,
                user_role=user_role,
            ):
                if event["type"] == "chunk":
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "done":
                    done_data = event
            
            if not done_data:
                done_data = {"type": "done", "answer": "", "contexts": [], "sources": [], "confidence": "低", "features": {}, "summary_text": None, "model_name": settings.LLM_MODEL}

            # 保存对话摘要
            if done_data.get("summary_text"):
                summary_msg = Message(
                    session_id=gen_session.id,
                    role="summary",
                    content=done_data["summary_text"],
                )
                gen_db.add(summary_msg)
                gen_db.commit()
                logger.info(f"对话摘要已保存到 DB: {done_data['summary_text'][:50]}...")
            
            # 保存 assistant 消息
            assistant_message = Message(
                session_id=gen_session.id,
                role="assistant",
                content=done_data.get("answer", ""),
                sources=json.dumps(done_data.get("sources", []), ensure_ascii=False),
                confidence=done_data.get("confidence"),
                features=json.dumps(done_data.get("features", {}), ensure_ascii=False),
                token_usage=json.dumps(done_data.get("token_usage", {}), ensure_ascii=False),
            )
            gen_db.add(assistant_message)
            gen_db.commit()
            gen_db.refresh(assistant_message)

            # 发送 done
            done_msg = json.dumps({
                'type': 'done',
                'answer': done_data.get("answer", ""),
                'sources': done_data.get("sources", []),
                'session_id': gen_session.id,
                'message_id': assistant_message.id,
                'confidence': done_data.get("confidence"),
                'features': done_data.get("features", {}),
                'token_usage': done_data.get("token_usage", {}),
            }, ensure_ascii=False)
            yield f"data: {done_msg}\n\n"

            # 答案验证
            if qa_service.use_answer_verification:
                try:
                    verification = answer_verifier.verify(
                        answer=done_data.get("answer", ""),
                        contexts=done_data.get("contexts", []),
                        question=request.content,
                        use_ai=True,
                        model_name=done_data.get("model_name", settings.LLM_MODEL),
                    )
                    if not verification["is_valid"]:
                        logger.warning(f"答案验证不通过: {verification['issues']}")
                        yield f"data: {json.dumps({'type': 'verification', 'is_valid': False, 'issues': verification['issues'], 'ai_reason': verification.get('ai_reason', ''), 'confidence': verification['confidence']}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'verification', 'is_valid': True, 'confidence': verification['confidence']}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.warning(f"答案验证异常: {e}")
            
            # 增加今日提问计数
            if user_role != UserRole.ADMIN.value:
                user_for_update = gen_db.query(User).filter(User.id == user_id).first()
                if user_for_update:
                    user_for_update.questions_today += 1
                    gen_db.commit()
            
            # 记录问题统计
            record_question_stat(request.content, gen_db)
            gen_db.commit()
            
        except Exception as e:
            print(f"[DIAG] generate() 异常: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            logger.error(f"流式问答失败：{str(e)}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            print("[DIAG] generate() 结束，关闭 gen_db", file=sys.stderr, flush=True)
            gen_db.close()
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions", response_model=list[SessionResponse])
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的会话列表"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    
    result = []
    for session in sessions:
        message_count = db.query(Message).filter(
            Message.session_id == session.id
        ).count()
        
        result.append(SessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            message_count=message_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        ))
    
    return result


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse)
def submit_message_feedback(
    message_id: int,
    feedback: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提交消息反馈（点赞/点踩）
    
    用于评估 AI 回答质量，帮助优化系统
    """
    if feedback.feedback not in ["up", "down"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="反馈值必须是 'up' 或 'down'"
        )
    
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    
    session = db.query(ChatSession).filter(
        ChatSession.id == message.session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此消息")
    
    message.feedback = feedback.feedback
    db.commit()
    
    logger.info(f"用户 {current_user.username} 对消息 {message_id} 提交反馈: {feedback.feedback}")
    
    return FeedbackResponse(
        message_id=message_id,
        feedback=feedback.feedback,
        success=True,
    )


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新会话"""
    session = ChatSession(
        user_id=current_user.id,
        title=session_data.title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定会话的消息列表"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    
    messages = db.query(Message).filter(
        Message.session_id == session_id,
        Message.role.in_(["user", "assistant"]),
    ).order_by(Message.created_at.asc()).all()
    
    result = []
    for msg in messages:
        sources = None
        if msg.sources:
            try:
                sources = json.loads(msg.sources)
            except:
                sources = None

        features = None
        if msg.features:
            try:
                features = json.loads(msg.features)
            except:
                features = None

        token_usage = None
        if msg.token_usage:
            try:
                token_usage = json.loads(msg.token_usage)
            except:
                token_usage = None
        
        result.append(MessageResponse(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            sources=sources,
            confidence=msg.confidence,
            features=features,
            token_usage=token_usage,
            feedback=msg.feedback,
            created_at=msg.created_at,
        ))
    
    return result


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除指定会话及其所有消息"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    
    db.query(Message).filter(Message.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    
    return {"success": True, "message": "会话已删除"}


@router.get("/stats")
def get_public_stats(db: Session = Depends(get_db)):
    """
    获取公开统计数据（无需认证）
    """
    total_documents = db.query(func.count(Document.id)).scalar() or 0

    total_questions = db.query(func.sum(QuestionStat.count)).scalar() or 0

    total_feedback = db.query(func.count(Message.id)).filter(
        Message.feedback.isnot(None)
    ).scalar() or 0

    positive_feedback = db.query(func.count(Message.id)).filter(
        Message.feedback == "up"
    ).scalar() or 0

    satisfaction = round((positive_feedback / total_feedback * 100), 1) if total_feedback > 0 else 0

    return {
        "totalDocuments": total_documents,
        "totalQuestions": total_questions,
        "satisfaction": satisfaction,
    }


@router.get("/quick-questions")
def get_quick_questions(
    limit: int = 6,
    db: Session = Depends(get_db)
):
    """
    获取热门问题作为快速提问建议（无需认证）
    """
    results = db.query(
        QuestionStat.content,
        QuestionStat.count.label("count")
    ).order_by(
        desc("count")
    ).limit(limit).all()

    return [row.content for row in results]


@router.get("/feature-status")
def get_feature_status(
    db: Session = Depends(get_db)
):
    """
    获取当前功能启用状态（无需认证）
    """
    from app.models import ModelConfig, SystemSetting

    def get_setting(key: str, default: str = "false") -> str:
        setting = db.query(SystemSetting).filter(
            SystemSetting.setting_key == key
        ).first()
        return setting.setting_value if setting else default

    # 获取 LLM 模型配置
    active_llm = db.query(ModelConfig).filter(
        ModelConfig.model_type == "llm",
        ModelConfig.is_active == True
    ).first()
    llm_configured = active_llm is not None

    # 获取 Reranker 模型配置
    active_reranker = db.query(ModelConfig).filter(
        ModelConfig.model_type == "reranker",
        ModelConfig.is_active == True
    ).first()
    reranker_configured = active_reranker is not None

    query_expansion_enabled = get_setting("query_expansion_enabled", "false") == "true"
    answer_verification_enabled = get_setting("answer_verification_enabled", "false") == "true"
    conversation_summary_enabled = get_setting("conversation_summary_enabled", "true") == "true"
    reranking_enabled = get_setting("reranking_enabled", "true") == "true"

    return {
        "query_expansion": {
            "enabled": query_expansion_enabled,
            "llm_available": llm_configured,
            "active": query_expansion_enabled and llm_configured,
        },
        "conversation_summary": {
            "enabled": conversation_summary_enabled,
            "llm_available": llm_configured,
            "active": conversation_summary_enabled and llm_configured,
        },
        "answer_verification": {
            "enabled": answer_verification_enabled,
            "llm_available": llm_configured,
            "active": answer_verification_enabled and llm_configured,
        },
        "reranking": {
            "enabled": reranking_enabled,
            "api_available": reranker_configured,
            "active": reranking_enabled,
            "model_name": active_reranker.model_name if active_reranker else None,
        },
    }


def _set_setting(db: Session, key: str, value: str, description: str = ""):
    """设置系统配置"""
    from app.models import SystemSetting
    from datetime import datetime
    setting = db.query(SystemSetting).filter(
        SystemSetting.setting_key == key
    ).first()
    if setting:
        setting.setting_value = value
        setting.updated_at = datetime.now()
    else:
        setting = SystemSetting(
            setting_key=key,
            setting_value=value,
            description=description,
        )
        db.add(setting)
    db.commit()


@router.post("/feature-toggle")
def toggle_feature(
    feature: str,
    enabled: bool,
    db: Session = Depends(get_db)
):
    """
    切换功能启用状态（需要认证）
    """
    from app.models import ModelConfig

    active_llm = db.query(ModelConfig).filter(
        ModelConfig.model_type == "llm",
        ModelConfig.is_active == True
    ).first()
    llm_configured = active_llm is not None

    active_reranker = db.query(ModelConfig).filter(
        ModelConfig.model_type == "reranker",
        ModelConfig.is_active == True
    ).first()
    reranker_configured = active_reranker is not None

    if feature == "query_expansion":
        _set_setting(db, "query_expansion_enabled", str(enabled).lower(), "查询扩展功能开关")
        return {
            "feature": feature,
            "enabled": enabled,
            "active": enabled and llm_configured,
            "message": f"查询扩展已{'启用' if enabled else '禁用'}",
        }
    elif feature == "answer_verification":
        _set_setting(db, "answer_verification_enabled", str(enabled).lower(), "答案验证功能开关")
        return {
            "feature": feature,
            "enabled": enabled,
            "active": enabled and llm_configured,
            "message": f"答案验证已{'启用' if enabled else '禁用'}",
        }
    elif feature == "conversation_summary":
        _set_setting(db, "conversation_summary_enabled", str(enabled).lower(), "对话摘要功能开关")
        return {
            "feature": feature,
            "enabled": enabled,
            "active": enabled and llm_configured,
            "message": f"对话摘要已{'启用' if enabled else '禁用'}",
        }
    elif feature == "reranking":
        _set_setting(db, "reranking_enabled", str(enabled).lower(), "重排序功能开关")
        return {
            "feature": feature,
            "enabled": enabled,
            "active": enabled,
            "message": f"重排序已{'启用' if enabled else '禁用'}",
        }
    else:
        return {
            "feature": feature,
            "enabled": False,
            "active": False,
            "message": f"未知功能: {feature}",
        }


@router.get("/model-info")
def get_model_info(
    db: Session = Depends(get_db)
):
    """
    获取当前使用的模型信息（无需认证）
    """
    from app.models import ModelConfig

    # 获取 LLM 模型
    active_llm = db.query(ModelConfig).filter(
        ModelConfig.model_type == "llm",
        ModelConfig.is_active == True
    ).first()

    llm_model_name = active_llm.model_name if active_llm else settings.LLM_MODEL

    # 获取 Embedding 模型
    active_embedding = db.query(ModelConfig).filter(
        ModelConfig.model_type == "embedding",
        ModelConfig.is_active == True
    ).first()

    embedding_model_name = active_embedding.model_name if active_embedding else settings.EMBEDDING_MODEL

    return {
        "llm_model_name": llm_model_name,
        "embedding_model_name": embedding_model_name,
        "provider": "tongyiqianwen",
    }


@router.get("/announcement")
def get_active_announcement(db: Session = Depends(get_db)):
    """
    获取当前激活的公告（无需认证）
    
    返回最新的激活公告，用于用户首次进入网站时弹窗显示
    """
    announcement = db.query(Announcement).filter(
        Announcement.is_active == True
    ).order_by(Announcement.created_at.desc()).first()
    
    if not announcement:
        return None
    
    return {
        "id": announcement.id,
        "title": announcement.title,
        "content": announcement.content,
        "is_popup": announcement.is_popup,
        "show_once": announcement.show_once,
        "created_at": announcement.created_at
    }


@router.post("/eval-retrieve")
def eval_retrieve(
    request: ChatAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检索评测接口"""
    from app.services.retrieval_service import RetrievalService

    retrieval_service = RetrievalService()
    # 检索质量评测：使用数据库配置的完整链路
    retrieval_service.use_semantic_cache = False
    retrieval_service.use_quality_filter = True
    results = retrieval_service.retrieve(
        question=request.content,
        top_k=request.top_k,
        db=db,
        use_expansion=False,
        user_role=current_user.role.value if current_user else None,
    )

    return {
        "results": [
            {
                "content": r.get("child_content", "") or r.get("parent_content", "") or r.get("content", ""),
                "source": r.get("source", ""),
                "score": r.get("score", 0.0),
                "document_id": r.get("document_id", 0),
            }
            for r in results
        ]
    }
