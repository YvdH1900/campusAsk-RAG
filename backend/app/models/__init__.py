"""
数据库模型定义
==============
定义所有 SQLAlchemy ORM 模型，包括：
1. User - 用户模型（含角色）
2. ChatSession - 对话会话
3. Message - 对话消息
4. Document - 知识库文档
5. Announcement - 公告模型
6. SystemSetting - 系统设置模型
7. LoginRecord - 登录记录模型
8. ModelConfig - 模型配置模型
9. QuestionStat - 问题统计模型
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean, Date, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


def get_beijing_time():
    """获取当前北京时间"""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    """
    用户模型
    存储用户基本信息和角色权限
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(100), unique=True, nullable=True, index=True, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="哈希密码")
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), default=UserRole.STUDENT, nullable=False, comment="用户角色")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    pending_approval = Column(Boolean, default=False, nullable=False, comment="是否待审核（教师注册）")
    approval_status = Column(String(20), default="approved", nullable=False, comment="审核状态: pending/approved/rejected")
    ban_until = Column(DateTime, default=None, nullable=True, comment="封禁截止时间")
    can_modify_profile = Column(Boolean, default=True, nullable=False, comment="是否允许修改个人信息")
    max_questions_per_day = Column(Integer, default=100, nullable=False, comment="每日最大提问次数")
    max_uploads_per_day = Column(Integer, default=10, nullable=False, comment="每日最大上传文件次数")
    questions_today = Column(Integer, default=0, nullable=False, comment="今日已提问次数")
    uploads_today = Column(Integer, default=0, nullable=False, comment="今日已上传次数")
    last_reset_date = Column(Date, default=None, nullable=True, comment="上次重置计数日期")
    current_session_id = Column(String(100), default=None, nullable=True, index=True, comment="当前登录会话 ID")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    uploaded_documents = relationship("Document", back_populates="uploader", foreign_keys="Document.uploaded_by")
    reviewed_documents = relationship("Document", back_populates="reviewer", foreign_keys="Document.reviewed_by")


class ChatSession(Base):
    """
    对话会话模型
    存储用户的一次完整对话
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    title = Column(String(200), nullable=False, comment="会话标题")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    """
    对话消息模型
    存储单条问答消息
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True, comment="会话ID")
    role = Column(String(20), nullable=False, comment="消息角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    sources = Column(Text, nullable=True, comment="引用来源 (JSON 格式)")
    confidence = Column(String(20), nullable=True, comment="答案置信度: 高/中/低")
    features = Column(Text, nullable=True, comment="功能状态 (JSON 格式)")
    token_usage = Column(Text, nullable=True, comment="Token 使用详情 (JSON 格式)")
    feedback = Column(String(10), nullable=True, comment="用户反馈：up/down")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")

    session = relationship("ChatSession", back_populates="messages")


class Document(Base):
    """
    知识库文档模型
    存储上传的文档及其处理状态
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_size = Column(Integer, default=0, nullable=False, comment="文件大小 (字节)")
    category = Column(String(50), nullable=True, comment="文档分类")
    description = Column(Text, nullable=True, comment="文档描述")
    status = Column(String(20), default="pending", nullable=False, comment="处理状态: pending/processing/completed/failed/split")
    review_status = Column(String(20), default="pending", nullable=False, comment="审核状态: pending/approved/rejected")
    split_group_id = Column(String(100), nullable=True, index=True, comment="拆分组ID（同源子文档共享同一ID）")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="审核人 ID")
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")
    reject_reason = Column(Text, nullable=True, comment="驳回理由")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="上传人 ID")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="上传时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")

    uploader = relationship("User", back_populates="uploaded_documents", foreign_keys=[uploaded_by])
    reviewer = relationship("User", back_populates="reviewed_documents", foreign_keys=[reviewed_by])


class Announcement(Base):
    """
    公告模型
    存储网站公告信息
    """
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="公告标题")
    content = Column(Text, nullable=False, comment="公告内容")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_popup = Column(Boolean, default=True, nullable=False, comment="是否弹窗显示")
    show_once = Column(Boolean, default=True, nullable=False, comment="是否只显示一次")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")


class SystemSetting(Base):
    """
    系统设置模型
    存储网站全局开关配置
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True, comment="设置键")
    setting_value = Column(String(500), nullable=True, comment="设置值")
    description = Column(String(500), nullable=True, comment="设置描述")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")


class LoginRecord(Base):
    """
    登录记录模型
    记录用户登录信息
    """
    __tablename__ = "login_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户 ID")
    username = Column(String(50), nullable=False, comment="用户名")
    login_time = Column(DateTime, default=get_beijing_time, nullable=False, comment="登录时间")
    ip_address = Column(String(50), nullable=True, comment="IP 地址")
    user_agent = Column(String(500), nullable=True, comment="浏览器信息")
    success = Column(Boolean, default=True, nullable=False, comment="登录是否成功")
    failure_reason = Column(String(200), nullable=True, comment="失败原因")

    user = relationship("User")


class ModelConfig(Base):
    """
    模型配置模型
    存储语言模型和向量模型的配置信息
    """
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_type = Column(String(20), nullable=False, comment="模型类型: llm/embedding")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    api_key = Column(String(500), nullable=False, comment="API密钥")
    api_base_url = Column(String(500), nullable=True, comment="API基础URL")
    dimension = Column(Integer, nullable=True, comment="向量维度（仅 embedding 模型）")
    is_active = Column(Boolean, default=False, nullable=False, comment="是否启用")
    is_default = Column(Boolean, default=False, nullable=False, comment="是否默认")
    config = Column(JSON, nullable=True, comment="额外配置 (JSON)")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")


class ParentChunk(Base):
    """
    父块存储模型
    存储文档的父块内容（章节级上下文），子块向量仍存 Milvus
    
    检索时：子块在 Milvus 中匹配 → 通过 parent_id 回查此表获取完整父块内容
    """
    __tablename__ = "parent_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True, comment="文档ID")
    parent_id = Column(String(100), nullable=False, index=True, comment="父块ID（如 p0, p1）")
    parent_content = Column(Text, nullable=False, comment="父块完整内容")
    split_group_id = Column(String(100), nullable=True, index=True, comment="拆分组ID")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="更新时间")

    document = relationship("Document", backref="parent_chunks")


class QuestionStat(Base):
    """
    问题统计模型
    持久化记录每个问题的提问次数，不随会话删除而减少
    """
    __tablename__ = "question_stats"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content = Column(String(500), nullable=False, index=True, comment="问题内容")
    count = Column(Integer, default=1, nullable=False, comment="提问次数")
    created_at = Column(DateTime, default=get_beijing_time, nullable=False, comment="首次提问时间")
    updated_at = Column(DateTime, default=get_beijing_time, onupdate=get_beijing_time, nullable=False, comment="最后更新时间")
