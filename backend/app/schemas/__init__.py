"""
Pydantic 数据模型
=================
定义 API 请求和响应的数据验证模型
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from datetime import datetime
from app.models import UserRole


class UserBase(BaseModel):
    """用户基础模型"""
    username: str
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    """用户注册请求"""
    password: str
    role: UserRole = UserRole.STUDENT


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserUpdate(BaseModel):
    """用户信息更新请求"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None


class UserLimitUpdate(BaseModel):
    """用户限制更新请求（管理员用）"""
    max_questions_per_day: Optional[int] = None
    max_uploads_per_day: Optional[int] = None
    can_modify_profile: Optional[bool] = None


class UserBanRequest(BaseModel):
    """用户封禁请求（管理员用）"""
    ban_until: Optional[datetime] = None
    reason: Optional[str] = None


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    role: UserRole
    is_active: bool
    pending_approval: bool = False
    approval_status: str = "approved"
    ban_until: Optional[datetime] = None
    can_modify_profile: bool = True
    max_questions_per_day: int = 100
    max_uploads_per_day: int = 10
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """登录响应 Token"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageCreate(BaseModel):
    """发送消息请求"""
    content: str
    session_id: Optional[int] = None


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    session_id: int
    role: str
    content: str
    sources: Optional[List[str]] = None
    confidence: Optional[str] = None
    features: Optional[Dict[str, str]] = None
    token_usage: Optional[Dict[str, int]] = None
    feedback: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    """创建会话请求"""
    title: str


class SessionResponse(BaseModel):
    """会话响应"""
    id: int
    user_id: int
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""
    filename: str
    category: Optional[str] = None
    description: Optional[str] = None


class DocumentReviewRequest(BaseModel):
    """文档审核请求"""
    action: str  # approve / reject
    reason: Optional[str] = None


class DocumentResponse(BaseModel):
    """文档响应"""
    id: int
    filename: str
    category: Optional[str] = None
    description: Optional[str] = None
    file_size: int = 0
    status: str
    review_status: str
    reject_reason: Optional[str] = None
    uploaded_by: Optional[int] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatAskRequest(BaseModel):
    """RAG 问答请求"""
    content: str
    session_id: Optional[int] = None
    stream: bool = False
    top_k: int = 5


class ChatAskResponse(BaseModel):
    """RAG 问答响应（非流式）"""
    answer: str
    sources: List[str]
    context_count: int
    session_id: int
    message_id: int
    confidence: Optional[str] = None
    features: Optional[Dict[str, str]] = None


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    feedback: str  # "up" or "down"


class FeedbackResponse(BaseModel):
    """用户反馈响应"""
    message_id: int
    feedback: str
    success: bool = True

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """分页响应基础模型"""
    total: int
    page: int
    page_size: int
    pages: int


class PaginatedUserResponse(PaginatedResponse):
    """分页用户响应"""
    items: List[UserResponse]


class PaginatedDocumentResponse(PaginatedResponse):
    """分页文档响应"""
    items: List[DocumentResponse]


class PasswordResetRequest(BaseModel):
    """密码重置请求"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """密码重置确认"""
    token: str
    new_password: str


# ==================== 公告相关 Schema ====================

class AnnouncementCreate(BaseModel):
    """创建公告请求"""
    title: str
    content: str
    is_popup: bool = True
    show_once: bool = True


class AnnouncementUpdate(BaseModel):
    """更新公告请求"""
    title: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None
    is_popup: Optional[bool] = None
    show_once: Optional[bool] = None


class AnnouncementResponse(BaseModel):
    """公告响应模型"""
    id: int
    title: str
    content: str
    is_active: bool
    is_popup: bool
    show_once: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 系统设置相关 Schema ====================

class SystemSettingResponse(BaseModel):
    """系统设置响应模型"""
    setting_key: str
    setting_value: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SystemSettingUpdate(BaseModel):
    """更新系统设置请求"""
    setting_value: str


# ==================== 模型配置相关 Schema ====================

class ModelConfigCreate(BaseModel):
    """创建模型配置请求"""
    model_config = {'protected_namespaces': ()}
    model_type: str  # llm / embedding
    model_name: str
    api_key: str
    api_base_url: Optional[str] = None
    dimension: Optional[int] = None  # 向量维度（仅 embedding 模型）
    config: Optional[dict] = None


class ModelConfigUpdate(BaseModel):
    """更新模型配置请求"""
    model_config = {'protected_namespaces': ()}
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    dimension: Optional[int] = None
    config: Optional[dict] = None


class ModelConfigResponse(BaseModel):
    """模型配置响应模型"""
    model_config = {'protected_namespaces': (), 'from_attributes': True}
    id: int
    model_type: str
    model_name: str
    api_key: str  # 脱敏显示
    api_base_url: Optional[str] = None
    dimension: Optional[int] = None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ModelTestRequest(BaseModel):
    """模型测试请求"""
    model_config = {'protected_namespaces': ()}
    model_type: str
    model_name: str
    api_key: str
    api_base_url: Optional[str] = None
    dimension: Optional[int] = None


class ModelTestResponse(BaseModel):
    """模型测试响应"""
    success: bool
    message: str
    latency_ms: Optional[int] = None
    actual_dimension: Optional[int] = None


# ==================== 登录记录相关 Schema ====================

class LoginRecordResponse(BaseModel):
    """登录记录响应模型"""
    id: int
    user_id: int
    username: str
    login_time: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    failure_reason: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedLoginRecordResponse(PaginatedResponse):
    """分页登录记录响应"""
    items: List[LoginRecordResponse]
