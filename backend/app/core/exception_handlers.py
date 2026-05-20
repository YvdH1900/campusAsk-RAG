"""
全局异常处理器
===============
统一捕获和处理所有异常，返回标准化的错误响应
支持：
- 自定义业务异常
- FastAPI内置异常（HTTPException, RequestValidationError）
- 未预期的系统异常
- 详细错误日志记录
- 请求追踪ID关联
"""

import traceback
import logging
from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from datetime import datetime

from app.core.response import error_response
from app.core.exceptions import (
    BaseAppException,
    BusinessException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ValidationException,
    RateLimitException,
    ExternalServiceException,
    DatabaseException,
)

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器
    
    捕获所有未处理的异常，返回统一格式的错误响应
    
    Args:
        request: FastAPI请求对象
        exc: 异常实例
        
    Returns:
        标准化的JSON错误响应
    """
    request_id = getattr(request.state, 'request_id', None)
    
    import sys
    print(f"[DIAG-EH] 捕获异常: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    
    if isinstance(exc, BaseAppException):
        return await handle_business_exception(request, exc, request_id)
    
    elif isinstance(exc, (HTTPException, StarletteHTTPException)):
        return await handle_http_exception(request, exc, request_id)
    
    elif isinstance(exc, RequestValidationError):
        return await handle_validation_error(request, exc, request_id)
    
    else:
        return await handle_unexpected_exception(request, exc, request_id)


async def handle_business_exception(
    request: Request,
    exc: BaseAppException,
    request_id: str = None
) -> JSONResponse:
    """
    处理自定义业务异常
    
    记录警告级别日志，返回业务错误信息
    """
    logger.warning(
        f"业务异常 [{exc.code}]: {exc.message}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "detail": exc.detail,
            **exc.extra
        }
    )
    
    response_data = error_response(
        code=exc.code,
        message=exc.message,
        detail=_should_show_detail() and exc.detail or None
    )
    
    if request_id:
        response_data["request_id"] = request_id
    
    return JSONResponse(
        status_code=exc.code,
        content=response_data
    )


async def handle_http_exception(
    request: Request,
    exc: HTTPException,
    request_id: str = None
) -> JSONResponse:
    """
    处理HTTP异常（404、405等）
    """
    logger.warning(
        f"HTTP异常 [{exc.status_code}]: {exc.detail}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    response_data = error_response(
        code=exc.status_code,
        message=exc.detail or "请求失败",
        detail=None
    )
    
    if request_id:
        response_data["request_id"] = request_id
        response_data["path"] = request.url.path
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_data
    )


async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
    request_id: str = None
) -> JSONResponse:
    """
    处理请求数据验证错误（Pydantic验证失败）
    """
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        loc = ' -> '.join(str(l) for l in error.get('loc', []))
        msg = error.get('msg', '验证失败')
        error_messages.append(f"{loc}: {msg}")
    
    detail_msg = "; ".join(error_messages)
    
    logger.warning(
        f"数据验证失败: {detail_msg}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": errors
        }
    )
    
    response_data = error_response(
        code=422,
        message="请求数据格式不正确",
        detail=_should_show_detail() and detail_msg or None
    )
    
    if request_id:
        response_data["request_id"] = request_id
    
    return JSONResponse(
        status_code=422,
        content=response_data
    )


async def handle_unexpected_exception(
    request: Request,
    exc: Exception,
    request_id: str = None
) -> JSONResponse:
    """
    处理未预期的系统异常
    
    记录完整的错误堆栈，返回通用错误信息（隐藏内部细节）
    """
    error_trace = traceback.format_exc()
    
    logger.error(
        f"未预期异常: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
            "traceback": error_trace
        },
        exc_info=True
    )
    
    response_data = error_response(
        code=500,
        message="服务器内部错误，请稍后重试",
        detail=_should_show_detail() and f"{type(exc).__name__}: {str(exc)}" or None
    )
    
    if request_id:
        response_data["request_id"] = request_id
    
    return JSONResponse(
        status_code=500,
        content=response_data
    )


def _should_show_detail() -> bool:
    """
    是否显示详细错误信息
    
    开发环境显示详细信息便于调试
    生产环境隐藏内部细节保证安全
    
    Returns:
        bool: 是否显示详情
    """
    from app.core.config import settings
    import os
    
    debug_mode = getattr(settings, 'DEBUG', False)
    is_dev = os.getenv('ENVIRONMENT', 'development') == 'development'
    
    return debug_mode or is_dev
