"""
认证 API 路由
============
提供用户认证相关接口：
1. POST /api/auth/register - 用户注册
2. POST /api/auth/login - 用户登录
3. GET /api/auth/me - 获取当前用户信息
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token, create_reset_token, decode_reset_token
from app.core.dependencies import get_current_user
from app.core.validators import validate_password_strength
from app.models import User, UserRole, SystemSetting, LoginRecord
from app.schemas import UserCreate, UserLogin, UserResponse, Token, UserUpdate, PasswordResetRequest, PasswordResetConfirm
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

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

def record_login(db: Session, user: User, ip_address: str = None, user_agent: str = None, success: bool = True, failure_reason: str = None):
    """记录登录记录"""
    login_record = LoginRecord(
        user_id=user.id,
        username=user.username,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        failure_reason=failure_reason
    )
    db.add(login_record)
    db.commit()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    用户注册
    
    创建新用户账号，支持学生和教师角色选择。
    教师角色需要管理员审核通过后才能使用。
    """
    # 检查注册开关
    registration_enabled = get_system_setting(db, SETTING_REGISTRATION_ENABLED, "true")
    if registration_enabled != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="网站注册已关闭，请稍后再试"
        )
    
    existing_user = db.query(User).filter(
        (User.username == user_data.username) |
        (User.email == user_data.email if user_data.email else False)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在"
        )
    
    # 验证密码强度
    is_valid, error_msg = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    is_teacher_pending = False
    approval_status = "approved"
    
    if user_data.role == UserRole.TEACHER:
        is_teacher_pending = True
        approval_status = "pending"
        role = UserRole.TEACHER
    else:
        role = UserRole.STUDENT
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=role,
        pending_approval=is_teacher_pending,
        approval_status=approval_status,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db), request: Request = None):
    """
    用户登录
    
    验证用户名密码，检查审核状态和封禁状态，返回 JWT Token 和用户信息。
    """
    user = db.query(User).filter(User.username == user_data.username).first()
    
    # 获取客户端IP地址
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    # 检查登录开关（管理员除外）
    if user and user.role != UserRole.ADMIN:
        login_enabled = get_system_setting(db, SETTING_LOGIN_ENABLED, "true")
        if login_enabled != "true":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="网站登录已关闭，请联系管理员"
            )
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        # 记录失败登录尝试
        if user:
            record_login(db, user, ip_address=ip_address, user_agent=user_agent, success=False, failure_reason="用户名或密码错误")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.role == UserRole.TEACHER and user.pending_approval:
        record_login(db, user, ip_address=ip_address, user_agent=user_agent, success=False, failure_reason="教师账号正在审核中")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="教师账号正在审核中，请等待管理员审核通过"
        )
    
    if user.approval_status == "rejected":
        record_login(db, user, ip_address=ip_address, user_agent=user_agent, success=False, failure_reason="账号审核未通过")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的账号审核未通过，请联系管理员"
        )
    
    if not user.is_active:
        record_login(db, user, ip_address=ip_address, user_agent=user_agent, success=False, failure_reason="用户已被禁用")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    if user.ban_until and user.ban_until > datetime.utcnow():
        record_login(db, user, ip_address=ip_address, user_agent=user_agent, success=False, failure_reason=f"用户已被封禁至 {user.ban_until.strftime('%Y-%m-%d %H:%M:%S')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户已被封禁至 {user.ban_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    # 生成新的会话 ID
    new_session_id = str(uuid.uuid4())
    
    # 检查是否有旧会话，如果有则会被踢下线
    if user.current_session_id:
        logger.info(f"用户 {user.username} 的旧会话 {user.current_session_id} 将被新会话 {new_session_id} 替换")
    
    # 更新用户的当前会话 ID
    user.current_session_id = new_session_id
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # 记录成功登录
    record_login(db, user, ip_address=ip_address, user_agent=user_agent, success=True)
    
    # 在 token 中加入 session_id
    access_token = create_access_token(data={"sub": str(user.id), "session_id": new_session_id})
    
    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息
    
    需要携带有效的 Bearer Token。
    """
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新当前用户信息
    
    用户可以修改用户名、邮箱或密码。
    重要信息（用户名、邮箱）不能与其他用户重复。
    """
    # 检查是否允许修改个人信息
    if not current_user.can_modify_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的账号已被禁止修改个人信息，请联系管理员"
        )
    
    if user_data.username is not None and user_data.username != current_user.username:
        existing_user = db.query(User).filter(
            User.username == user_data.username,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被其他用户使用"
            )
        
        current_user.username = user_data.username
    
    if user_data.email is not None and user_data.email != current_user.email:
        existing_user = db.query(User).filter(
            User.email == user_data.email,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他用户使用"
            )
        
        current_user.email = user_data.email
    
    if user_data.password is not None:
        # 验证密码强度
        is_valid, error_msg = validate_password_strength(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        current_user.hashed_password = get_password_hash(user_data.password)
    
    current_user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)):
    """
    用户登出
    
    客户端应清除本地存储的 token 和用户信息。
    JWT 是无状态的，服务端不维护 session，
    此接口主要用于记录登出日志和扩展（如 token 黑名单）。
    """
    return None


@router.post("/password-reset/request")
def request_password_reset(
    reset_data: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    请求密码重置
    
    根据邮箱查找用户，如果用户存在则生成随机密码。
    如果用户被禁止修改个人信息，则无法重置密码。
    """
    import os
    import secrets
    import string
    
    user = db.query(User).filter(User.email == reset_data.email).first()
    
    if not user:
        # 为了安全，即使用户不存在也返回成功，防止枚举邮箱
        return {"message": "如果邮箱已注册，重置密码将发送到您的邮箱"}
    
    # 检查是否允许修改个人信息
    if not user.can_modify_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的账号已被禁止修改个人信息，无法重置密码，请联系管理员"
        )
    
    # 生成随机密码：10 位包含大小写字母和数字
    alphabet = string.ascii_letters + string.digits
    random_password = ''.join(secrets.choice(alphabet) for _ in range(10))
    
    # 更新用户密码
    user.hashed_password = get_password_hash(random_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # 直接返回随机密码，供用户复制
    return {
        "message": "密码重置成功，请尽快修改密码以确保账号安全",
        "random_password": random_password,
    }


@router.post("/password-reset/confirm")
def confirm_password_reset(
    confirm_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    确认密码重置
    
    使用重置 Token 验证并设置新密码。
    """
    payload = decode_reset_token(confirm_data.token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置链接无效或已过期"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置链接无效"
        )
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证密码强度
    is_valid, error_msg = validate_password_strength(confirm_data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    user.hashed_password = get_password_hash(confirm_data.new_password)
    user.updated_at = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"用户 {user.username} 密码重置成功")
    
    return {"message": "密码重置成功，请使用新密码登录"}
