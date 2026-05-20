"""
自定义异常类
=============
定义业务异常层次结构，支持：
- 统一错误码管理
- 多语言错误消息
- 异常链追踪
- 结构化日志记录
"""

from typing import Optional, Any, Dict


class BaseAppException(Exception):
    """
    应用基础异常类
    
    所有业务异常的基类，提供统一的异常处理接口
    
    Attributes:
        code: 错误码（HTTP状态码或业务错误码）
        message: 用户友好的错误描述
        detail: 详细错误信息（用于日志和开发调试）
        extra: 附加信息（可选，用于传递上下文数据）
    """
    
    def __init__(
        self,
        message: str = "服务器内部错误",
        code: int = 500,
        detail: Optional[str] = None,
        **extra: Any
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail or message
        self.extra = extra
        
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（用于API响应）
        
        Returns:
            包含错误信息的字典
        """
        result = {
            "code": self.code,
            "message": self.message,
            "detail": self.detail
        }
        if self.extra:
            result.update(self.extra)
        return result
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class BusinessException(BaseAppException):
    """
    业务逻辑异常
    
    用于处理业务规则违反的情况，如：
    - 参数校验失败
    - 权限不足
    - 资源状态不合法
    
    Example:
        raise BusinessException("余额不足", code=400, detail="当前余额100元，需要200元")
    """
    pass


class NotFoundException(BaseAppException):
    """
    资源未找到异常
    
    当请求的资源不存在时抛出
    
    Example:
        raise NotFoundException("用户不存在", detail=f"user_id={user_id}")
    """
    
    def __init__(self, message: str = "资源不存在", resource: Optional[str] = None, **extra):
        detail = f"{resource}不存在" if resource else message
        super().__init__(message=message, code=404, detail=detail, **extra)


class UnauthorizedException(BaseAppException):
    """
    未授权异常
    
    用户未登录或Token无效时抛出
    
    Example:
        raise UnauthorizedException("登录已过期")
    """
    
    def __init__(self, message: str = "未授权访问", **extra):
        super().__init__(message=message, code=401, **extra)


class ForbiddenException(BaseAppException):
    """
    禁止访问异常
    
    用户已认证但权限不足时抛出
    
    Example:
        raise ForbiddenException("无权操作此资源")
    """
    
    def __init__(self, message: str = "权限不足", **extra):
        super().__init__(message=message, code=403, **extra)


class ValidationException(BaseAppException):
    """
    数据验证异常
    
    请求数据不符合要求时抛出
    
    Example:
        raise ValidationException("邮箱格式错误", field="email")
    """
    
    def __init__(self, message: str = "数据验证失败", field: Optional[str] = None, **extra):
        super().__init__(message=message, code=422, field=field, **extra)


class RateLimitException(BaseAppException):
    """
    请求频率限制异常
    
    超过API调用频率限制时抛出
    
    Example:
        raise RateLimitException("操作过于频繁", retry_after=60)
    """
    
    def __init__(
        self,
        message: str = "请求过于频繁",
        retry_after: int = 60,
        **extra
    ):
        super().__init__(message=message, code=429, retry_after=retry_after, **extra)


class ExternalServiceException(BaseAppException):
    """
    外部服务调用异常
    
    第三方服务（LLM、向量库等）调用失败时抛出
    
    Example:
        raise ExternalServiceException(
            "AI服务暂时不可用",
            service="dashscope",
            original_error="Connection timeout"
        )
    """
    
    def __init__(
        self,
        message: str = "外部服务不可用",
        service: Optional[str] = None,
        original_error: Optional[str] = None,
        **extra
    ):
        detail = f"{service}服务错误: {original_error}" if service and original_error else message
        super().__init__(message=message, code=502, detail=detail, service=service, **extra)


class DatabaseException(BaseAppException):
    """
    数据库操作异常
    
    数据库查询、写入失败时抛出
    
    Example:
        raise DatabaseException("数据库连接失败", operation="query_users")
    """
    
    def __init__(
        self,
        message: str = "数据库操作失败",
        operation: Optional[str] = None,
        original_error: Optional[str] = None,
        **extra
    ):
        detail = f"数据库{operation}失败: {original_error}" if operation and original_error else message
        super().__init__(message=message, code=500, detail=detail, operation=operation, **extra)


class CacheException(BaseAppException):
    """
    缓存操作异常
    
    Redis等缓存服务异常时抛出
    """
    
    def __init__(
        self,
        message: str = "缓存服务异常",
        operation: Optional[str] = None,
        **extra
    ):
        super().__init__(message=message, code=500, detail=message, operation=operation, **extra)


class ConfigurationException(BaseAppException):
    """
    配置错误异常
    
    缺少必要的环境变量或配置项时抛出
    
    Example:
        raise ConfigurationException("缺少API密钥", config_key="DASHSCOPE_API_KEY")
    """
    
    def __init__(self, message: str = "配置错误", config_key: Optional[str] = None, detail: Optional[str] = None, **extra):
        if detail is None:
            detail = f"缺少配置项: {config_key}" if config_key else message
        super().__init__(message=message, code=500, detail=detail, config_key=config_key, **extra)
