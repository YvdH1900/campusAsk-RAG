"""
问答服务（RAG Pipeline 企业级增强版）
==================================
整合检索、提示词构建、LLM 调用的完整问答流程
支持：
- 单轮问答
- 多轮对话（含历史上下文）
- 流式输出
- 重试机制
- 超时控制
- 优雅降级
- 摘要压缩
- 置信度评估
- 回答缓存
- 语义缓存（相似问题）
- 意图识别（动态策略）
- 答案验证（质量检测）
- 智能对话历史管理
"""

import logging
import time
import re
from typing import List, Dict, Optional, Generator
from dashscope import Generation
from app.core.config import settings
from app.services.retrieval_service import RetrievalService
from app.services.prompt_template import PromptTemplate
from app.services.cache_service import cache_service
from app.services.summary_service import SummaryService
from app.services.semantic_cache import semantic_cache
from app.services.answer_verifier import answer_verifier
from app.services.intent_classifier import intent_classifier

logger = logging.getLogger(__name__)


class QAService:
    """问答服务（企业级增强版）"""

    def __init__(self):
        """初始化问答服务"""
        self.retriever = RetrievalService()
        self.max_retries = 3
        self.base_delay = 1
        self.timeout = 30  # API 超时（秒）
        self.answer_cache_ttl = 86400  # 回答缓存 24 小时
        self.use_semantic_cache = True  # 是否启用语义缓存
        self.use_answer_verification = False  # 默认禁用
        self.use_conversation_summary = True  # 默认启用
        self.max_total_retries = 5  # 最大总重试次数（跨所有调用）
        self._last_features = {}  # 记录上次使用的功能状态

    def _load_settings_from_db(self, db=None):
        """从数据库加载功能开关配置"""
        if db:
            try:
                from app.models import SystemSetting
                for key, attr in [
                    ("answer_verification_enabled", "use_answer_verification"),
                    ("conversation_summary_enabled", "use_conversation_summary"),
                ]:
                    setting = db.query(SystemSetting).filter(
                        SystemSetting.setting_key == key
                    ).first()
                    if setting:
                        setattr(self, attr, setting.setting_value == "true")
                        logger.info(f"从数据库加载配置 {key}: {getattr(self, attr)}")
            except Exception as e:
                logger.warning(f"读取功能配置失败: {e}")

    def _get_current_model_name(self, db=None) -> str:
        """
        获取当前使用的模型名称
        
        优先从数据库读取激活的配置，如果没有则使用环境变量中的默认值
        
        Returns:
            模型名称
        """
        if db:
            try:
                from app.models import ModelConfig
                active_llm = db.query(ModelConfig).filter(
                    ModelConfig.model_type == "llm",
                    ModelConfig.is_active == True
                ).first()
                
                if active_llm:
                    return active_llm.model_name
            except Exception as e:
                logger.warning(f"读取数据库模型配置失败：{e}")
        
        # 如果数据库没有配置，使用环境变量中的默认值
        return settings.LLM_MODEL

    def _get_answer_cache_key(self, question: str) -> str:
        """
        生成回答缓存
        
        Args:
            question: 用户问题
            
        Returns:
            缓存键
        """
        import hashlib
        question_hash = hashlib.md5(question.encode("utf-8")).hexdigest()
        return f"answer:{question_hash}"

    def _call_llm_with_retry(self, messages, model_name, stream=False, timeout=None):
        """
        带指数退避重试和超时控制的 LLM 调用
        
        Args:
            messages: 消息列表
            model_name: 模型名称（动态传入）
            stream: 是否流式输出
            timeout: 超时时间（秒）
            
        Returns:
            LLM 响应
        """
        timeout = timeout or self.timeout
        last_error = None
        attempt_retries = 0
        
        logger.info(f"开始调用 LLM: {model_name} (流式={stream})")
        
        for attempt in range(self.max_retries):
            try:
                response = Generation.call(
                    model=model_name,
                    messages=messages,
                    stream=stream,
                    result_format="message",
                    timeout=timeout,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.2,
                    enable_search=False,
                    incremental_output=True,
                )

                # 流式调用返回 generator，状态码在迭代时才能验证
                if stream:
                    logger.info(f"LLM 流式调用已发起: {model_name}")
                    return response
                
                # 非流式调用检查状态码
                if response.status_code == 200:
                    answer_len = len(response.output.choices[0].message.content) if response.output.choices else 0
                    logger.info(f"LLM 调用成功: {model_name}, 回答长度={answer_len}")
                    return response
                
                error_msg = response.message
                logger.warning(f"LLM API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                last_error = error_msg
                
            except Exception as e:
                logger.warning(f"LLM API 调用异常 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                last_error = str(e)
            
            if attempt < self.max_retries - 1:
                attempt_retries += 1
                if attempt_retries >= self.max_total_retries:
                    raise RuntimeError(f"LLM 调用失败，已达最大总重试次数 {self.max_total_retries}")
                delay = self.base_delay * (2 ** attempt)
                logger.info(f"等待 {delay} 秒后重试...")
                time.sleep(delay)
        
        raise RuntimeError(f"LLM 调用失败，已重试 {self.max_retries} 次: {last_error}")

    def _merge_cross_document_context(self, contexts: List[Dict]) -> List[Dict]:
        """
        跨子文档上下文合并：同源子文档的 chunk 合并为完整上下文
        
        企业级策略：大文件拆分成多个子文档后，用户问题可能涉及多个部分的内容。
        此方法检测检索结果中来自同一原文档的多个子文档 chunk，
        将它们的 parent_content 合并，确保 LLM 看到完整的跨部分上下文。
        
        Args:
            contexts: 检索到的上下文列表
            
        Returns:
            合并后的上下文列表
        """
        if not contexts:
            return contexts

        # 按 split_group_id 分组
        doc_groups = {}
        for ctx in contexts:
            group_id = ctx.get("split_group_id") or f"doc_{ctx.get('document_id', 'unknown')}"
            doc_groups.setdefault(group_id, []).append(ctx)

        # 如果所有 chunk 都来自不同文档，无需合并
        if len(doc_groups) <= 1:
            return contexts

        merged_contexts = []
        for group_id, group_chunks in doc_groups.items():
            if len(group_chunks) == 1:
                # 只有一个 chunk，无需合并
                merged_contexts.append(group_chunks[0])
            else:
                # 多个 chunk 来自同一原文档，合并 parent_content
                # 按 document_id 和 parent_id 去重后合并
                seen_parents = set()
                parent_contents = []
                for ctx in group_chunks:
                    parent_id = ctx.get("parent_id")
                    if parent_id and parent_id not in seen_parents:
                        seen_parents.add(parent_id)
                        # parent_content 可能为空，回退到 child_content
                        content_text = ctx.get("parent_content") or ctx.get("child_content", "")
                        if content_text:
                            parent_contents.append(content_text)

                # 构建合并后的上下文
                merged_content = "\n\n---\n\n".join(parent_contents) if parent_contents else ""
                merged_ctx = group_chunks[0].copy()
                merged_ctx["content"] = merged_content
                merged_ctx["parent_content"] = merged_content
                merged_ctx["child_content"] = merged_content[:500]  # 保留子块内容用于展示
                merged_ctx["_merged"] = True
                merged_ctx["_source_count"] = len(group_chunks)
                merged_contexts.append(merged_ctx)

        # 按 score 重新排序
        merged_contexts.sort(key=lambda x: x.get("score", 0), reverse=True)

        if len(doc_groups) > 1:
            logger.info(
                f"跨子文档上下文合并: {len(contexts)} 个 chunk -> "
                f"{len(merged_contexts)} 个合并上下文, 涉及 {len(doc_groups)} 个拆分组"
            )

        return merged_contexts

    def _calculate_confidence(self, contexts: List[Dict]) -> str:
        """
        根据检索结果计算置信度
        
        Args:
            contexts: 检索到的上下文列表
            
        Returns:
            置信度（高/中/低）
        """
        if not contexts:
            return "低"
        
        # 基于最高相关度分数计算置信度
        max_score = max(ctx.get("score", 0) for ctx in contexts)
        
        if max_score >= 0.6:
            return "高"
        elif max_score >= 0.4:
            return "中"
        else:
            return "低"

    def _is_answer_cacheable(self, answer: str) -> bool:
        """
        检查答案是否值得缓存
        
        排除"未找到信息"类无价值回答，防止语义缓存被低质量答案污染。
        
        Args:
            answer: LLM 生成的回答
            
        Returns:
            是否值得缓存
        """
        if not answer:
            return False
        
        # 不可缓存的模式：LLM 表示无法从知识库找到信息
        not_found_patterns = [
            "无法找到",
            "没有找到相关",
            "未找到相关",
            "没有找到关于",
            "知识库中未包含",
            "未提及",
            "无法基于",
            "我无法回答",
            "抱歉，我目前无法",
        ]
        for pattern in not_found_patterns:
            if pattern in answer:
                logger.info(f"答案包含'未找到'模式('{pattern}')，跳过缓存")
                return False
        
        return True

    def _build_answer_from_contexts(self, question: str, contexts: List[Dict]) -> str:
        """从检索上下文直接构造回答（不依赖 LLM）

        将多个检索结果的 content 拼接为完整回答，按得分排序，
        每条标注来源，上限 2000 字符。
        """
        if not contexts:
            return "抱歉，我暂时无法从校园知识库中找到相关信息。请尝试换一种提问方式。"

        parts = []
        seen = set()
        total_len = 0
        max_len = 2000

        for ctx in contexts:
            content = (ctx.get("content") or "").strip()
            if not content or content in seen:
                continue
            seen.add(content)

            source = ctx.get("source", "未知来源")
            snippet = content[:500] if len(content) > 500 else content

            if total_len + len(snippet) + len(source) + 10 > max_len:
                remaining = max_len - total_len - len(source) - 10
                if remaining > 50:
                    snippet = content[:remaining]
                else:
                    break

            parts.append(f"【来源：{source}】\n{snippet}")
            total_len += len(snippet) + len(source) + 10

        if not parts:
            return "抱歉，检索到的内容无法有效回答该问题。请尝试换一种提问方式。"

        return "\n\n".join(parts)

    def _handle_chat_question(self, question: str) -> Dict:
        """
        处理闲聊类型问题
        
        Args:
            question: 用户问题
            
        Returns:
            直接回答
        """
        question_lower = question.lower()
        
        if any(g in question_lower for g in ["你好", "您好", "嗨", "hi", "hello"]):
            return {
                "answer": "你好！我是校园智能助手，可以为您解答关于校园的各类问题，如课程安排、考试信息、校园设施等。请问有什么我可以帮助您的？",
                "sources": [],
                "context_count": 0,
                "confidence": "高",
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
        elif any(g in question_lower for g in ["谢谢", "感谢"]):
            return {
                "answer": "不客气！如果还有其他问题，随时可以问我。祝您学习愉快！",
                "sources": [],
                "context_count": 0,
                "confidence": "高",
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
        elif any(g in question_lower for g in ["你是谁", "你叫什么"]):
            return {
                "answer": "我是校园智能助手，基于 RAG（检索增强生成）技术，能够基于校园知识库为您提供准确的信息服务。",
                "sources": [],
                "context_count": 0,
                "confidence": "高",
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
        else:
            return {
                "answer": "您好！我是校园智能助手，请问有什么校园相关的问题我可以帮助您？",
                "sources": [],
                "context_count": 0,
                "confidence": "高",
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }

    def ask(
        self,
        question: str,
        chat_history: Optional[List[Dict]] = None,
        top_k: int = 5,
        db=None,
        user_role: Optional[str] = None,
    ) -> Dict:
        """
        单轮问答（非流式）
        
        Args:
            question: 用户问题
            chat_history: 对话历史
            top_k: 检索结果数量
            db: 数据库会话
            user_role: 用户角色（用于权限过滤）
            
        Returns:
            {
                "answer": "AI 回答",
                "sources": [来源列表],
                "context_count": 检索到的上下文数量,
                "confidence": "置信度",
            }
        """
        # 1. 意图识别
        intent_result = intent_classifier.classify(question)
        intent = intent_result["intent"]
        strategy = intent_result["strategy"]
        
        # 如果是闲聊，直接回答
        if strategy.get("direct_answer"):
            return self._handle_chat_question(question)

        # 2. 语义缓存检查
        if self.use_semantic_cache:
            cached_answer = semantic_cache.search_similar(question, db=db)
            if cached_answer:
                logger.info(f"语义缓存命中: {question[:30]}...")
                return cached_answer

        # 3. 尝试精确缓存
        cache_key = self._get_answer_cache_key(question)
        cached_answer = cache_service.get(cache_key)
        if cached_answer:
            logger.info(f"回答缓存命中: {question[:30]}...")
            return cached_answer

        # 4. 加载功能开关配置
        self._load_settings_from_db(db)

        # 5. 检索相关文档（带权限过滤）
        contexts = self.retriever.retrieve(
            question=question,
            top_k=top_k,
            db=db,
            user_role=user_role,
        )

        # 5.5 跨子文档上下文合并：同源子文档的 chunk 合并为完整上下文
        contexts = self._merge_cross_document_context(contexts)

        if not contexts:
            return {
                "answer": self._build_answer_from_contexts(question, []),
                "sources": [],
                "context_count": 0,
                "confidence": "低",
                "features": {},
                "summary_text": None,
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }

        # 5. 智能对话历史管理
        current_model = self._get_current_model_name(db)
        summary_text = None
        if chat_history:
            chat_history, summary_text = self._smart_manage_history(
                chat_history,
                question,
                contexts,
                current_model,
            )

        # 6. 构建提示词（传入当前模型名称）
        messages = PromptTemplate.build_messages_for_llm(
            question=question,
            contexts=contexts,
            chat_history=chat_history,
            model_name=current_model,
        )

        # 7. 调用 LLM（带超时和重试）
        token_usage = {}
        try:
            response = self._call_llm_with_retry(
                messages, 
                model_name=current_model,
                stream=False, 
                timeout=self.timeout
            )
            answer = response.output.choices[0].message.content
            # 统计 token 使用量
            token_usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }
        except Exception as e:
            logger.error(f"LLM 调用失败，使用检索上下文直接回答: {str(e)}")
            feature_status = self.retriever.get_feature_status()
            return {
                "answer": self._build_answer_from_contexts(question, contexts),
                "sources": [ctx["source"] for ctx in contexts],
                "context_count": len(contexts),
                "confidence": "低",
                "features": {
                    "rerank_method": feature_status.get("rerank_method", "unknown"),
                    "reranker_model": feature_status.get("reranker_model", "未配置"),
                },
                "summary_text": summary_text,
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }

        # 8. 答案验证（优先 AI 验证，失败降级规则验证）
        if self.use_answer_verification:
            verification = answer_verifier.verify(answer, contexts, question, use_ai=True, model_name=current_model)
            
            if not verification["is_valid"]:
                logger.warning(f"答案验证失败: {verification['issues']}")
                # 尝试验证失败时的处理
                if verification["context_coverage"] < 0.3:
                    # 上下文覆盖率太低，尝试重新检索
                    logger.info("上下文覆盖率过低，尝试重新检索")
                    contexts = self.retriever.retrieve(
                        question=question,
                        top_k=top_k * 2,
                        db=db,
                        user_role=user_role,
                    )
                    
                    if contexts:
                        messages = PromptTemplate.build_messages_for_llm(
                            question=question,
                            contexts=contexts,
                            chat_history=chat_history,
                            model_name=current_model,
                        )
                        
                        try:
                            response = self._call_llm_with_retry(
                                messages,
                                model_name=current_model,
                                stream=False,
                                timeout=self.timeout,
                            )
                            answer = response.output.choices[0].message.content
                            # 更新 token 使用量（重新生成）
                            token_usage = {
                                "input_tokens": getattr(response.usage, "input_tokens", 0),
                                "output_tokens": getattr(response.usage, "output_tokens", 0),
                                "total_tokens": getattr(response.usage, "total_tokens", 0),
                            }
                        except Exception as e:
                            logger.error(f"重新生成答案失败: {str(e)}")

        # 9. 计算置信度
        confidence = self._calculate_confidence(contexts)

        # 10. 获取功能使用状态
        feature_status = self.retriever.get_feature_status()
        self._last_features = {
            "rerank_method": feature_status.get("rerank_method", "unknown"),
            "reranker_model": feature_status.get("reranker_model", "未配置"),
        }

        result = {
            "answer": answer,
            "sources": [ctx["source"] for ctx in contexts],
            "context_count": len(contexts),
            "confidence": confidence,
            "features": self._last_features,
            "summary_text": summary_text,
            "token_usage": token_usage,
        }

        # 11. 缓存回答（高置信度 + 答案有效性检查）
        if confidence == "高" and self._is_answer_cacheable(answer):
            cache_service.set(cache_key, result, self.answer_cache_ttl)
            # 同时存储到语义缓存
            semantic_cache.store(question, result, db=db)
            logger.info(f"高置信度回答已缓存: {question[:30]}...")

        return result

    def ask_stream(
        self,
        question: str,
        chat_history: Optional[List[Dict]] = None,
        top_k: int = 5,
        db=None,
        user_role: Optional[str] = None,
    ) -> Generator:
        """
        流式问答（yield 结构化事件字典）
        
        事件类型:
            {"type": "chunk", "content": "文本片段"}
            {"type": "done", "contexts": [...], "sources": [...], 
             "confidence": "高", "features": {...}, "summary_text": "..."}
        
        Args:
            question: 用户问题
            chat_history: 对话历史
            top_k: 检索结果数量
            db: 数据库会话
            user_role: 用户角色（用于权限过滤）
        """
        contexts = []
        sources = []
        summary_text = None
        current_model = self._get_current_model_name(db)
        full_text = ""

        # 1. 意图识别
        intent_result = intent_classifier.classify(question)
        strategy = intent_result["strategy"]
        
        # 如果是闲聊，直接回答
        if strategy.get("direct_answer"):
            full_text = self._handle_chat_question(question)["answer"]
            yield {"type": "chunk", "content": full_text}
            yield self._build_stream_done(full_text, [], [], current_model, None, {})
            return

        # 2. 加载功能开关配置
        self._load_settings_from_db(db)

        # 3. 检索相关文档（带权限过滤）
        contexts = self.retriever.retrieve(
            question=question,
            top_k=top_k,
            db=db,
            user_role=user_role,
        )
        
        # 3.5 跨子文档上下文合并
        contexts = self._merge_cross_document_context(contexts)
        sources = list(dict.fromkeys(ctx.get("source", "未知文档") for ctx in contexts))

        if not contexts:
            full_text = self._build_answer_from_contexts(question, [])
            yield {"type": "chunk", "content": full_text}
            yield self._build_stream_done(full_text, [], [], current_model, None, {})
            return

        # 3. 智能对话历史管理
        if chat_history:
            chat_history, summary_text = self._smart_manage_history(
                chat_history,
                question,
                contexts,
                current_model,
            )

        # 4. 构建提示词
        messages = PromptTemplate.build_messages_for_llm(
            question=question,
            contexts=contexts,
            chat_history=chat_history,
            model_name=current_model,
        )

        # 5. 流式调用 LLM
        token_usage = {}
        try:
            logger.info(f"开始流式 LLM 调用: {current_model}")
            response = self._call_llm_with_retry(
                messages, 
                model_name=current_model,
                stream=True, 
                timeout=self.timeout
            )

            chunk_count = 0
            full_answer_chunks = []
            last_chunk = None
            for chunk in response:
                # 检测流式 API 错误（HTTP 4xx/5xx 等非 200 状态码）
                if hasattr(chunk, 'status_code') and chunk.status_code != 200:
                    error_code = getattr(chunk, 'code', '')
                    error_message = getattr(chunk, 'message', '')
                    request_id = getattr(chunk, 'request_id', '')
                    raise RuntimeError(
                        f"LLM API 错误 (HTTP {chunk.status_code})"
                        f"{': ' + error_code if error_code else ''}"
                        f"{': ' + error_message if error_message else ''}"
                        f"{' [request_id=' + request_id + ']' if request_id else ''}"
                    )
                
                if not hasattr(chunk, 'output') or chunk.output is None:
                    continue
                
                # 兼容 text 格式（output.text）和 message 格式（output.choices）
                if hasattr(chunk.output, 'text') and chunk.output.text:
                    content = chunk.output.text
                    chunk_count += 1
                    full_answer_chunks.append(content)
                    yield {"type": "chunk", "content": content}
                    last_chunk = chunk
                    continue
                
                if not hasattr(chunk.output, 'choices') or not chunk.output.choices:
                    continue
                
                try:
                    choice = chunk.output.choices[0]
                    # 兼容 delta 格式（新版 DashScope API）和 message 格式（旧版）
                    msg_or_delta = choice.message if hasattr(choice, 'message') and choice.message else None
                    if msg_or_delta is None:
                        msg_or_delta = choice.get("delta") if hasattr(choice, 'get') else None
                    
                    if not msg_or_delta:
                        continue
                    
                    content = None
                    if hasattr(msg_or_delta, 'content'):
                        content = msg_or_delta.content
                    elif isinstance(msg_or_delta, dict):
                        content = msg_or_delta.get("content")
                    
                    if content:
                        chunk_count += 1
                        full_answer_chunks.append(content)
                        yield {"type": "chunk", "content": content}
                    
                    last_chunk = chunk
                except (IndexError, AttributeError) as e:
                    logger.warning(f"解析流式 chunk 失败：{e}")
                    continue
            
            full_text = "".join(full_answer_chunks)
            
            # LLM 返回了流式响应但无实质内容，按 API 异常处理
            if not full_text.strip():
                raise RuntimeError(
                    f"LLM 流式响应无内容: 共收到 {chunk_count} 个有效 chunk，"
                    f"但均无文本内容 (chunk_count={chunk_count}, total_chunks=unknown)"
                )
            
            # 从最后一个 chunk 提取 token 使用量
            if last_chunk and hasattr(last_chunk, 'usage') and last_chunk.usage is not None:
                token_usage = {
                    "input_tokens": getattr(last_chunk.usage, "input_tokens", 0),
                    "output_tokens": getattr(last_chunk.usage, "output_tokens", 0),
                    "total_tokens": getattr(last_chunk.usage, "total_tokens", 0),
                }
            
            # 如果流式响应没有返回 usage，使用估算值（企业级 fallback）
            if not token_usage.get("total_tokens"):
                # 使用更准确的估算：中文字符约 1.5 token/字，英文约 0.25 token/字
                def estimate_tokens(text):
                    if not text:
                        return 0
                    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
                    other_chars = len(text) - chinese_chars
                    return max(1, int(chinese_chars * 1.5 + other_chars * 0.25))
                
                input_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
                output_tokens = estimate_tokens(full_text)
                token_usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }
                logger.info(f"使用估算 token: 输入={input_tokens}, 输出={output_tokens}")
            
            logger.info(f"流式 LLM 调用完成: {current_model}, 共 {chunk_count} 个 chunk, token: {token_usage.get('total_tokens', 0)}")
        except Exception as e:
            logger.error(f"LLM 调用失败，使用检索上下文直接回答: {str(e)}")
            full_text = self._build_answer_from_contexts(question, contexts)
            token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            yield {"type": "chunk", "content": full_text}

        # 6. yield 元数据供调用方后处理
        yield self._build_stream_done(full_text, contexts, sources, current_model, summary_text, token_usage)

    def _build_stream_done(self, full_text, contexts, sources, model_name, summary_text, token_usage=None):
        """构建 ask_stream 的 done 事件"""
        feature_status = self.retriever.get_feature_status()
        
        # 确保 token_usage 始终有有效值（企业级防御性编程）
        if not token_usage or not token_usage.get("total_tokens"):
            # 如果到这里还没有 token_usage，使用最简估算
            input_tokens = max(10, len(full_text) // 3)
            output_tokens = max(10, len(full_text) // 2)
            token_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }
            logger.info(f"最终 fallback token 估算: {token_usage}")
        
        return {
            "type": "done",
            "answer": full_text,
            "contexts": contexts,
            "sources": sources,
            "confidence": self._calculate_confidence(contexts),
            "features": {
                "rerank_method": feature_status.get("rerank_method", "unknown"),
                "reranker_model": feature_status.get("reranker_model", "未配置"),
            },
            "summary_text": summary_text,
            "model_name": model_name,
            "token_usage": token_usage,
        }

    def _smart_manage_history(
        self,
        chat_history: List[Dict],
        current_question: str,
        contexts: List[Dict],
        model_name: str = "qwen-plus",
    ) -> tuple:
        """
        智能管理对话历史
        
        Args:
            chat_history: 原始对话历史
            current_question: 当前问题
            contexts: 检索到的上下文
            model_name: AI 摘要使用的 LLM 模型名称
            
        Returns:
            (优化后的对话历史, 摘要文本或None)
        """
        # 1. 检查是否需要压缩
        if not SummaryService.should_compress(chat_history):
            return chat_history, None

        # 2. 如果关闭了对话摘要，直接截断保留最近的消息
        if not self.use_conversation_summary:
            # 保留最近 4 条消息（2 轮对话）
            normal_msgs = [m for m in chat_history if m.get("role") not in ("summary", "system")]
            recent = normal_msgs[-4:] if len(normal_msgs) > 4 else normal_msgs
            logger.info(f"对话摘要已关闭，截断保留最近 {len(recent)} 条消息")
            return recent, None

        # 3. 使用 AI 摘要压缩（优先 AI，失败降级截断）
        compressed = SummaryService.compress_history(chat_history, use_ai=True, model_name=model_name)
        
        # 提取摘要文本
        summary_text = None
        if compressed and compressed[0].get("role") == "system":
            summary_text = compressed[0]["content"]

        # 4. 保留最近的一轮对话（如果有的话），排除摘要/系统消息
        normal_msgs = [m for m in chat_history if m.get("role") not in ("summary", "system")]
        if len(normal_msgs) >= 2:
            recent_history = normal_msgs[-2:]
            compressed = compressed + recent_history

        logger.info(
            f"智能对话历史管理: {len(chat_history)} -> {len(compressed)} 条"
        )
        
        return compressed, summary_text
