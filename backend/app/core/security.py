"""
安全认证模块
===========
提供密码加密、JWT Token 生成和验证等安全相关功能。
使用 bcrypt 进行密码哈希，使用 python-jose 进行 JWT 处理。
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """
    将明文密码转换为哈希密码
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT Access Token
    
    JWT (JSON Web Token) 是一种用于身份验证的令牌格式。
    包含用户信息和过期时间，使用密钥签名防止篡改。
    
    Args:
        data: 要编码到 Token 中的数据，通常包含用户ID
              例如: {"sub": "user_id"}
        expires_delta: 可选的过期时间增量
                      如果不提供，使用配置中的默认值
    
    Returns:
        str: 编码后的 JWT Token 字符串
    
    Token 结构:
        - Header: 算法和令牌类型
        - Payload: 用户数据 + 过期时间
        - Signature: 使用 SECRET_KEY 签名
    
    示例:
        token = create_access_token(
            data={"sub": user.id},
            expires_delta=timedelta(hours=1)
        )
    """
    # 复制数据，避免修改原始字典
    to_encode = data.copy()
    
    # 计算过期时间
    # 如果提供了 expires_delta，使用它；否则使用配置中的默认值
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    
    # 将过期时间添加到载荷中
    to_encode.update({"exp": expire})
    
    # 使用密钥和算法编码 JWT Token
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def create_reset_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建密码重置 Token
    
    Args:
        data: 要编码的数据，通常包含用户ID和邮箱
        expires_delta: 可选的过期时间增量
    
    Returns:
        str: 编码后的重置 Token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "reset"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_reset_token(token: str) -> Optional[dict]:
    """
    解码并验证密码重置 Token
    
    Args:
        token: 重置 Token 字符串
    
    Returns:
        Optional[dict]: 解码成功返回 Token 数据，失败返回 None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "reset":
            return None
        return payload
    except JWTError:
        return None


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT Access Token
    
    用于从请求中提取 Token 并验证其有效性。
    会检查签名是否正确以及 Token 是否过期。
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        Optional[dict]: 解码成功返回 Token 中的数据字典
                       解码失败（Token 无效或过期）返回 None
    
    示例:
        payload = decode_access_token(token)
        if payload:
            user_id = payload["sub"]
        else:
            # Token 无效，要求重新登录
    """
    if not token or not isinstance(token, str):
        return None
    try:
        # 解码 Token，验证签名和过期时间
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        # JWTError 包括:
        # - ExpiredSignatureError: Token 已过期
        # - InvalidTokenError: Token 格式无效
        # - SignatureError: 签名不匹配
        return None
