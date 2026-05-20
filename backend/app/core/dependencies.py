"""
认证依赖模块
============
提供 FastAPI 依赖注入函数，用于：
1. 获取当前登录用户
2. 验证用户角色权限
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前登录用户
    
    从请求 Header 的 Authorization 中提取 Bearer Token，
    解码后查询数据库返回用户对象。
    
    Args:
        token: JWT Token（由 FastAPI 自动从 Header 提取）
        db: 数据库会话
    
    Returns:
        User: 当前登录的用户对象
    
    Raises:
        HTTPException 401: Token 无效或用户不存在
        HTTPException 403: 用户已被禁用
    """
    import sys
    print(f"[DIAG] get_current_user 调用, token={token[:10] if token else 'None'}...", file=sys.stderr, flush=True)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    # 验证 session_id 是否匹配
    token_session_id = payload.get("session_id")
    if token_session_id and user.current_session_id:
        if token_session_id != user.current_session_id:
            print(f"[DIAG] Session mismatch! Token session: {token_session_id}, DB session: {user.current_session_id}", file=sys.stderr, flush=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已失效，您的账号可能在其他地方登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    print(f"[DIAG] get_current_user 返回 user.id={user.id}, role={user.role}", file=sys.stderr, flush=True)
    return user


def get_current_user_optional(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    获取当前登录用户（可选，允许未认证）
    
    如果提供了有效的 Token，返回用户对象；
    如果没有 Token 或 Token 无效，返回 None。
    
    Args:
        token: JWT Token（可选）
        db: 数据库会话
    
    Returns:
        Optional[User]: 当前登录的用户对象，或 None
    """
    if token is None:
        return None
    
    try:
        payload = decode_access_token(token)
        if payload is None:
            return None
        
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None or not user.is_active:
            return None
        
        return user
    except Exception:
        return None


def require_role(*roles: UserRole):
    """
    角色权限验证装饰器
    
    检查当前用户是否具有指定角色之一。
    
    Args:
        *roles: 允许的角色列表
    
    Returns:
        依赖函数，用于 FastAPI Depends
    
    示例:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_only(current_user: User = Depends(get_current_user)):
            return {"msg": "管理员专属"}
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，需要更高角色权限"
            )
        return current_user
    
    return role_checker
