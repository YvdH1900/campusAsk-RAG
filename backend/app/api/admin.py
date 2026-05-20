"""
管理员 API 路由
==============
提供管理员专用功能：
1. GET /api/admin/stats - 获取系统统计数据
2. GET /api/admin/popular-questions - 获取热门问题 TOP 10
3. GET /api/admin/users - 获取所有用户列表
4. PUT /api/admin/users/{id}/limit - 限制用户（提问次数/上传次数）
5. POST /api/admin/users/{id}/ban - 封禁用户
6. POST /api/admin/users/{id}/unban - 解封用户
7. POST /api/admin/users/{id}/approve - 审核通过教师注册
8. POST /api/admin/users/{id}/reject - 审核驳回教师注册
9. 公告管理 - 公告增删改查
10. 系统设置管理 - 注册开关、登录开关
11. 模型配置管理 - LLM/Embedding 模型配置、连通性测试、向量库重建
12. 登录记录管理 - 查看登录日志
"""

import time
import json
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta
from typing import Optional, List
from math import ceil
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models import User, UserRole, ChatSession, Message, Document, Announcement, SystemSetting, LoginRecord, ModelConfig, QuestionStat

# 获取日志记录器
logger = logging.getLogger(__name__)
from app.utils.task_progress import progress_store, generate_task_id, TaskProgress
from app.schemas import (
    UserResponse, UserLimitUpdate, UserBanRequest, PaginatedUserResponse,
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
    SystemSettingResponse, SystemSettingUpdate,
    ModelConfigCreate, ModelConfigUpdate, ModelConfigResponse,
    ModelTestRequest, ModelTestResponse,
    LoginRecordResponse, PaginatedLoginRecordResponse
)

# 系统设置键定义
SETTING_REGISTRATION_ENABLED = "registration_enabled"
SETTING_LOGIN_ENABLED = "login_enabled"

def get_system_setting(db: Session, key: str, default_value: str = "true") -> str:
    """获取系统设置值"""
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    if setting:
        return setting.setting_value
    # 如果不存在，创建默认值
    new_setting = SystemSetting(
        setting_key=key,
        setting_value=default_value,
        description="系统设置"
    )
    db.add(new_setting)
    db.commit()
    return default_value

def set_system_setting(db: Session, key: str, value: str, description: str = ""):
    """设置系统设置值"""
    setting = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    if setting:
        setting.setting_value = value
        if description:
            setting.description = description
    else:
        setting = SystemSetting(
            setting_key=key,
            setting_value=value,
            description=description
        )
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting

router = APIRouter(prefix="/admin", tags=["管理员"])


def require_admin(current_user: User = Depends(get_current_user)):
    """验证管理员权限"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以访问"
        )
    return current_user


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取系统统计数据
    """
    total_questions = db.query(func.sum(QuestionStat.count)).scalar() or 0

    total_documents = db.query(func.count(Document.id)).scalar() or 0

    total_users = db.query(func.count(User.id)).scalar() or 0

    total_feedback = db.query(func.count(Message.id)).filter(
        Message.feedback.isnot(None)
    ).scalar() or 0

    positive_feedback = db.query(func.count(Message.id)).filter(
        Message.feedback == "up"
    ).scalar() or 0

    satisfaction = round((positive_feedback / total_feedback * 100), 1) if total_feedback > 0 else 0

    return {
        "totalQuestions": total_questions,
        "totalDocuments": total_documents,
        "totalUsers": total_users,
        "satisfaction": satisfaction,
    }


@router.get("/popular-questions")
def get_popular_questions(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取热门问题 TOP N
    """
    from app.models import QuestionStat
    
    results = db.query(
        QuestionStat.content,
        QuestionStat.count.label("count")
    ).order_by(
        desc("count")
    ).limit(limit).all()

    return [
        {"question": row.content, "count": row.count}
        for row in results
    ]


@router.get("/users", response_model=PaginatedUserResponse)
def get_all_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取所有用户列表（支持分页）
    
    管理员可以查看所有用户信息，包括审核状态和限制信息。
    """
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    total = query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedUserResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=users,
    )


@router.put("/users/{user_id}/limit", response_model=UserResponse)
def update_user_limits(
    user_id: int,
    limit_data: UserLimitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新用户限制
    
    可以设置用户的每日最大提问次数和上传次数。
    学生角色的上传限制始终为 0（不能上传文档）。
    可以禁止用户修改个人信息（包括密码）。
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能限制管理员账号"
        )
    
    if limit_data.max_questions_per_day is not None:
        user.max_questions_per_day = limit_data.max_questions_per_day
    
    if user.role == UserRole.STUDENT:
        user.max_uploads_per_day = 0
    elif limit_data.max_uploads_per_day is not None:
        user.max_uploads_per_day = limit_data.max_uploads_per_day
    
    # 更新个人信息修改权限
    if limit_data.can_modify_profile is not None:
        user.can_modify_profile = limit_data.can_modify_profile
    
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/users/{user_id}/ban", response_model=UserResponse)
def ban_user(
    user_id: int,
    ban_data: UserBanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    封禁用户
    
    可以设置封禁截止时间，不设置则永久封禁。
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能封禁管理员账号"
        )
    
    user.ban_until = ban_data.ban_until
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/users/{user_id}/unban", response_model=UserResponse)
def unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    解封用户
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.ban_until = None
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    审核通过教师注册
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能审核教师账号"
        )
    
    if not user.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户已经审核过了"
        )
    
    user.pending_approval = False
    user.approval_status = "approved"
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/users/{user_id}/reject", response_model=UserResponse)
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    审核驳回教师注册
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能审核教师账号"
        )
    
    if not user.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户已经审核过了"
        )
    
    user.pending_approval = False
    user.approval_status = "rejected"
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/users/{user_id}", response_model=dict)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除用户（级联删除相关信息）
    
    删除内容：
    - 用户的所有聊天记录
    - 用户的所有会话
    - 不删除用户上传的文档（保留数据库记录和文件）
    
    注意：不能删除管理员账号
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 不能删除管理员
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除管理员账号"
        )
    
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )
    
    try:
        # 1. 删除用户的所有消息
        db.query(Message).filter(
            Message.session_id.in_(
                db.query(ChatSession.id).filter(ChatSession.user_id == user_id)
            )
        ).delete(synchronize_session=False)
        
        # 2. 删除用户的所有会话
        db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(synchronize_session=False)
        
        # 注意：不删除用户上传的文档，保留数据库记录和文件
        # 文档可以通过文档管理功能单独删除
        
        logger.info(f"管理员 {current_user.username} 删除了用户 {user.username} (ID: {user_id})")
        
        # 3. 删除用户账号
        db.delete(user)
        db.commit()
        
        return {
            "message": "用户已删除",
            "deleted_user": user.username,
            "user_id": user_id
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"删除用户失败：{str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除用户失败：{str(e)}"
        )


# ==================== 公告管理 ====================

@router.get("/announcements", response_model=List[AnnouncementResponse])
def get_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取所有公告列表
    """
    announcements = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return announcements


@router.post("/announcements", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
def create_announcement(
    announcement_data: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建新公告
    """
    new_announcement = Announcement(
        title=announcement_data.title,
        content=announcement_data.content,
        is_popup=announcement_data.is_popup,
        show_once=announcement_data.show_once,
        is_active=True
    )
    db.add(new_announcement)
    db.commit()
    db.refresh(new_announcement)
    return new_announcement


@router.put("/announcements/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: int,
    announcement_data: AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新公告信息
    """
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="公告不存在"
        )
    
    if announcement_data.title is not None:
        announcement.title = announcement_data.title
    if announcement_data.content is not None:
        announcement.content = announcement_data.content
    if announcement_data.is_active is not None:
        announcement.is_active = announcement_data.is_active
    if announcement_data.is_popup is not None:
        announcement.is_popup = announcement_data.is_popup
    if announcement_data.show_once is not None:
        announcement.show_once = announcement_data.show_once
    
    db.commit()
    db.refresh(announcement)
    return announcement


@router.delete("/announcements/{announcement_id}", status_code=status.HTTP_200_OK)
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除公告
    """
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="公告不存在"
        )
    
    db.delete(announcement)
    db.commit()
    return {"success": True, "message": "公告已删除"}


@router.get("/announcements/active", response_model=List[AnnouncementResponse])
def get_active_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """
    获取当前活跃的公告（用于前端弹窗显示）
    返回所有需要弹窗显示的公告列表
    """
    announcements = db.query(Announcement).filter(
        Announcement.is_active == True,
        Announcement.is_popup == True
    ).order_by(Announcement.created_at.desc()).all()
    
    # 返回所有公告列表（如果没有公告，返回空列表而不是 404）
    return announcements if announcements else []


# ==================== 系统设置管理 ====================

@router.get("/settings", response_model=List[SystemSettingResponse])
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取所有系统设置
    """
    settings = db.query(SystemSetting).all()
    return settings


@router.get("/settings/registration-enabled", response_model=SystemSettingResponse)
def get_registration_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取注册开关状态
    """
    value = get_system_setting(db, SETTING_REGISTRATION_ENABLED, "true")
    return SystemSettingResponse(
        setting_key=SETTING_REGISTRATION_ENABLED,
        setting_value=value,
        description="网站注册开关，开启时允许新用户注册"
    )


@router.put("/settings/registration-enabled", response_model=SystemSettingResponse)
def set_registration_setting(
    setting_data: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    设置注册开关状态
    """
    if setting_data.setting_value not in ["true", "false"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="值必须是 'true' 或 'false'"
        )
    
    setting = set_system_setting(
        db, 
        SETTING_REGISTRATION_ENABLED, 
        setting_data.setting_value,
        "网站注册开关，开启时允许新用户注册"
    )
    return setting


@router.get("/settings/login-enabled", response_model=SystemSettingResponse)
def get_login_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取登录开关状态
    """
    value = get_system_setting(db, SETTING_LOGIN_ENABLED, "true")
    return SystemSettingResponse(
        setting_key=SETTING_LOGIN_ENABLED,
        setting_value=value,
        description="网站登录开关，关闭时除管理员外所有人无法登录"
    )


@router.put("/settings/login-enabled", response_model=SystemSettingResponse)
def set_login_setting(
    setting_data: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    设置登录开关状态
    """
    if setting_data.setting_value not in ["true", "false"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="值必须是 'true' 或 'false'"
        )
    
    setting = set_system_setting(
        db, 
        SETTING_LOGIN_ENABLED, 
        setting_data.setting_value,
        "网站登录开关，关闭时除管理员外所有人无法登录"
    )
    return setting


# ==================== 模型配置管理 ====================

@router.get("/model-configs", response_model=List[ModelConfigResponse])
def get_model_configs(
    model_type: Optional[str] = Query(None, description="按模型类型筛选: llm/embedding"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取模型配置列表
    """
    query = db.query(ModelConfig)
    if model_type:
        query = query.filter(ModelConfig.model_type == model_type)
    
    configs = query.order_by(ModelConfig.created_at.desc()).all()
    
    # 脱敏处理 API Key
    result = []
    for config in configs:
        response = ModelConfigResponse.model_validate(config)
        # 脱敏显示 API Key
        if response.api_key and len(response.api_key) > 8:
            response.api_key = response.api_key[:4] + "***" + response.api_key[-4:]
        result.append(response)
    
    return result


@router.post("/model-configs", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
def create_model_config(
    config_data: ModelConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建模型配置
    """
    if config_data.model_type not in ["llm", "embedding", "reranker"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模型类型必须是 'llm'、'embedding' 或 'reranker'"
        )
    
    # 检查是否已存在同名模型
    existing = db.query(ModelConfig).filter(
        and_(
            ModelConfig.model_type == config_data.model_type,
            ModelConfig.model_name == config_data.model_name
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"已存在名为 '{config_data.model_name}' 的{config_data.model_type}模型配置"
        )
    
    new_config = ModelConfig(
        model_type=config_data.model_type,
        model_name=config_data.model_name,
        api_key=config_data.api_key,
        api_base_url=config_data.api_base_url,
        config=config_data.config,
        is_active=False,
        is_default=False
    )
    
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    # 脱敏处理
    response = ModelConfigResponse.model_validate(new_config)
    if response.api_key and len(response.api_key) > 8:
        response.api_key = response.api_key[:4] + "***" + response.api_key[-4:]
    
    return response


@router.put("/model-configs/{config_id}", response_model=ModelConfigResponse)
def update_model_config(
    config_id: int,
    config_data: ModelConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新模型配置
    """
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型配置不存在"
        )
    
    # 允许修改配置，包括正在使用的配置
    # 激活操作会单独处理
    if config_data.model_name is not None:
        config.model_name = config_data.model_name
    if config_data.api_key is not None:
        config.api_key = config_data.api_key
    if config_data.api_base_url is not None:
        config.api_base_url = config_data.api_base_url
    if config_data.dimension is not None:
        config.dimension = config_data.dimension
    if config_data.config is not None:
        config.config = config_data.config
    
    db.commit()
    db.refresh(config)
    
    # 脱敏处理
    response = ModelConfigResponse.model_validate(config)
    if response.api_key and len(response.api_key) > 8:
        response.api_key = response.api_key[:4] + "***" + response.api_key[-4:]
    
    return response


@router.delete("/model-configs/{config_id}", status_code=status.HTTP_200_OK)
def delete_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除模型配置
    """
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型配置不存在"
        )
    
    if config.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除正在使用的模型配置，请先切换到其他配置"
        )
    
    db.delete(config)
    db.commit()
    return {"success": True, "message": "模型配置已删除"}


@router.post("/model-configs/test", response_model=ModelTestResponse)
def test_model_connection(
    test_data: ModelTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    测试模型连通性
    """
    start_time = time.time()
    
    try:
        if test_data.model_type == "llm":
            # 测试 LLM 模型
            import dashscope
            from dashscope import Generation
            
            original_key = os.environ.get("DASHSCOPE_API_KEY", "")
            os.environ["DASHSCOPE_API_KEY"] = test_data.api_key
            dashscope.api_key = test_data.api_key
            
            response = Generation.call(
                model=test_data.model_name,
                prompt="你好",
                max_tokens=10
            )
            
            os.environ["DASHSCOPE_API_KEY"] = original_key
            dashscope.api_key = original_key
            
            if response.status_code == 200:
                latency_ms = int((time.time() - start_time) * 1000)
                return ModelTestResponse(
                    success=True,
                    message="LLM 模型测试通过",
                    latency_ms=latency_ms
                )
            else:
                return ModelTestResponse(
                    success=False,
                    message=f"LLM 模型测试失败: {response.message}"
                )
        
        elif test_data.model_type == "embedding":
            # 测试 Embedding 模型
            import dashscope
            from dashscope import TextEmbedding
            
            original_key = os.environ.get("DASHSCOPE_API_KEY", "")
            os.environ["DASHSCOPE_API_KEY"] = test_data.api_key
            dashscope.api_key = test_data.api_key
            
            response = TextEmbedding.call(
                model=test_data.model_name,
                input="测试文本"
            )
            
            os.environ["DASHSCOPE_API_KEY"] = original_key
            dashscope.api_key = original_key
            
            if response.status_code == 200:
                latency_ms = int((time.time() - start_time) * 1000)
                return ModelTestResponse(
                    success=True,
                    message="Embedding 模型测试通过",
                    latency_ms=latency_ms
                )
            else:
                return ModelTestResponse(
                    success=False,
                    message=f"Embedding 模型测试失败: {response.message}"
                )
        
        elif test_data.model_type == "reranker":
            # 测试 Reranker 模型（API 调用测试）
            try:
                import dashscope
                from http import HTTPStatus
                
                # 临时设置 API Key
                original_key = dashscope.api_key
                dashscope.api_key = test_data.api_key
                
                try:
                    # 调用 Reranker API
                    response = dashscope.TextReRank.call(
                        model=test_data.model_name,
                        query="测试问题",
                        documents=["测试文档一", "测试文档二"],
                        top_n=2
                    )
                    
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status_code == HTTPStatus.OK:
                        return ModelTestResponse(
                            success=True,
                            message=f"Reranker API 测试通过",
                            latency_ms=latency_ms
                        )
                    else:
                        return ModelTestResponse(
                            success=False,
                            message=f"Reranker API 测试失败: {response.message}"
                        )
                finally:
                    # 恢复原始 API Key
                    dashscope.api_key = original_key
                    
            except Exception as e:
                return ModelTestResponse(
                    success=False,
                    message=f"Reranker API 测试异常: {str(e)}"
                )
        
        else:
            return ModelTestResponse(
                success=False,
                message="不支持的模型类型"
            )
    
    except Exception as e:
        return ModelTestResponse(
            success=False,
            message=f"测试异常: {str(e)}"
        )


@router.post("/model-configs/{config_id}/activate")
def activate_model_config(
    config_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    激活模型配置（切换模型）
    对于 Embedding 模型，需要重建向量库
    """
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型配置不存在"
        )
    
    # 测试连通性
    test_result = test_model_connection(
        ModelTestRequest(
            model_type=config.model_type,
            model_name=config.model_name,
            api_key=config.api_key,
            api_base_url=config.api_base_url
        ),
        db,
        current_user
    )
    
    if not test_result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"模型连通性测试失败: {test_result.message}"
        )
    
    # 切换模型
    if config.model_type == "embedding":
        # 对于 Embedding 模型，需要重建向量库
        # 创建任务对象用于追踪进度
        task_id = generate_task_id("rebuild_vector_store")
        task = TaskProgress(task_id=task_id, task_type="rebuild_vector_store", total=100)
        progress_store.add_task(task)
        
        # 创建后台任务，使用独立数据库会话
        background_tasks.add_task(
            rebuild_vector_store_with_db,
            task_id,
            config.id,
            config.model_name,
            config.api_key,
            config.api_base_url
        )
        
        # 先不更新配置状态，等待重建完成后再更新
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Embedding 模型切换请求已提交，向量库正在后台重建中，请稍后查看进度"
        }
    
    elif config.model_type == "reranker":
        # 对于 Reranker 模型，直接切换（无需重建数据）
        db.query(ModelConfig).filter(
            ModelConfig.model_type == "reranker",
            ModelConfig.is_active == True
        ).update({"is_active": False})
        config.is_active = True
        db.commit()
        
        return {
            "success": True,
            "message": "Reranker 模型切换成功，下次检索时将使用新模型"
        }
    
    else:
        # 对于 LLM 模型，直接切换
        db.query(ModelConfig).filter(ModelConfig.model_type == "llm", ModelConfig.is_active == True).update({"is_active": False})
        config.is_active = True
        db.commit()
        
        # 更新环境变量（确保重启后也能使用）
        os.environ["DASHSCOPE_API_KEY"] = config.api_key
        os.environ["LLM_MODEL"] = config.model_name
        
        return {
            "success": True,
            "message": "LLM 模型切换成功"
        }


@router.get("/model-configs/rebuild-progress/{task_id}")
def get_rebuild_progress(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取向量库重建进度
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="权限不足")
    
    task = progress_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task.to_dict()


def rebuild_vector_store(task_id: str, config_id: int, model_name: str, api_key: str, api_base_url: str, db: Session):
    """
    重建向量库（后台任务）
    """
    import dashscope
    from app.services.vector_store import VectorStore
    from app.services.document_processor import DocumentProcessor
    from app.models import Document, ModelConfig
    
    original_config_id = None
    original_model_name = None
    
    try:
        # 保存原始配置 ID，用于失败时恢复
        original_active = db.query(ModelConfig).filter(
            ModelConfig.model_type == "embedding",
            ModelConfig.is_active == True
        ).first()
        if original_active:
            original_config_id = original_active.id
            original_model_name = original_active.model_name
        
        progress_store.update_task(task_id, 0, "初始化", "正在准备重建环境")
        
        original_key = os.environ.get("DASHSCOPE_API_KEY", "")
        
        os.environ["DASHSCOPE_API_KEY"] = api_key
        dashscope.api_key = api_key
        
        progress_store.update_task(task_id, 10, "清空向量库", "正在删除现有向量数据")
        
        vector_store = VectorStore(db=db)
        vector_store.drop_collection()
        
        progress_store.update_task(task_id, 20, "查询文档", "正在获取所有已处理文档")
        
        documents = db.query(Document).filter(Document.status == "completed").all()
        total_docs = len(documents)
        
        if total_docs == 0:
            progress_store.complete_task(task_id, "没有需要重建的文档")
            os.environ["DASHSCOPE_API_KEY"] = original_key
            dashscope.api_key = original_key
            return
        
        progress_store.update_task(task_id, 30, "开始重建", f"共有 {total_docs} 个文档需要重建")
        
        processor = DocumentProcessor()
        success_count = 0
        failed_docs = []
        
        for idx, doc in enumerate(documents):
            try:
                stage_progress = 30 + int((idx / total_docs) * 65)
                progress_store.update_task(
                    task_id, 
                    stage_progress, 
                    "重建中", 
                    f"正在处理文档 {idx + 1}/{total_docs}: {doc.filename}"
                )
                
                processor.delete_document_vectors(doc.id, db=db)
                processor.process_document(doc, db)
                success_count += 1
                
            except Exception as doc_error:
                logger.error(f"文档 {doc.id} 重建失败：{str(doc_error)}")
                failed_docs.append(doc.filename)
        
        progress_store.update_task(task_id, 95, "清理优化", "正在清理孤儿向量")
        
        vector_store.delete_orphan_vectors()
        
        if failed_docs:
            error_msg = f"部分文档重建失败：{success_count}/{total_docs} 成功，{len(failed_docs)} 失败"
            if failed_docs:
                error_msg += f"\n失败文档：{', '.join(failed_docs[:5])}"
                if len(failed_docs) > 5:
                    error_msg += f" 等{len(failed_docs)}个文档"
            progress_store.fail_task(task_id, error_msg)
            
            logger.error(f"向量库重建部分失败：{error_msg}")
        else:
            progress_store.complete_task(task_id, f"向量库重建完成，共重建 {success_count} 个文档")
            logger.info(f"向量库重建成功：{success_count} 个文档")
        
        # 恢复原始配置
        os.environ["DASHSCOPE_API_KEY"] = original_key
        dashscope.api_key = original_key
        
    except Exception as e:
        logger.error(f"向量库重建失败：{str(e)}")
        error_message = f"重建失败：{str(e)}"
        progress_store.fail_task(task_id, error_message)
        
        # 失败回滚：恢复原始配置状态
        if original_config_id:
            try:
                db.query(ModelConfig).filter(
                    ModelConfig.model_type == "embedding",
                    ModelConfig.is_active == True
                ).update({"is_active": False})
                
                original_config = db.query(ModelConfig).filter(ModelConfig.id == original_config_id).first()
                if original_config:
                    original_config.is_active = True
                    db.commit()
                    logger.info(f"已回滚到原始配置：{original_model_name}")
            except Exception as rollback_error:
                logger.error(f"回滚配置失败：{str(rollback_error)}")


def rebuild_vector_store_with_db(task_id: str, config_id: int, model_name: str, api_key: str, api_base_url: str):
    """
    重建向量库（带独立数据库会话）
    """
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        rebuild_vector_store(task_id, config_id, model_name, api_key, api_base_url, db)
        
        # 重建完成后，更新模型配置状态
        if progress_store.get_task(task_id) and progress_store.get_task(task_id).status.value == "completed":
            config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
            if config:
                db.query(ModelConfig).filter(
                    ModelConfig.model_type == "embedding", 
                    ModelConfig.is_active == True
                ).update({"is_active": False})
                config.is_active = True
                db.commit()
                
                # 同步更新环境变量（确保重启后也能使用）
                os.environ["DASHSCOPE_API_KEY"] = config.api_key
                os.environ["EMBEDDING_MODEL"] = config.model_name
                if config.dimension:
                    os.environ["EMBEDDING_DIMENSION"] = str(config.dimension)
    finally:
        db.close()


# ==================== 登录记录管理 ====================

@router.get("/login-records", response_model=PaginatedLoginRecordResponse)
def get_login_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    success: Optional[bool] = Query(None, description="按登录结果筛选"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取登录记录列表（支持分页和筛选）
    """
    query = db.query(LoginRecord)
    
    if user_id:
        query = query.filter(LoginRecord.user_id == user_id)
    if success is not None:
        query = query.filter(LoginRecord.success == success)
    if start_time:
        query = query.filter(LoginRecord.login_time >= start_time)
    if end_time:
        query = query.filter(LoginRecord.login_time <= end_time)
    
    total = query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    
    records = query.order_by(LoginRecord.login_time.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedLoginRecordResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=records
    )


@router.delete("/login-records/cleanup")
def cleanup_login_records(
    days_to_keep: int = Query(30, ge=1, description="保留最近多少天的记录"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    清理旧的登录记录
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    deleted_count = db.query(LoginRecord).filter(LoginRecord.login_time < cutoff_date).delete()
    db.commit()
    
    return {"success": True, "message": f"已清理 {deleted_count} 条过期登录记录"}
