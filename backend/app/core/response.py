"""
统一API响应格式
================
定义标准化的API响应结构，确保所有接口返回格式一致
支持：
- 成功响应（data）
- 错误响应（error + message）
- 分页响应（data + pagination）
- 流式响应（SSE）
"""

from typing import Any, Optional, Generic, TypeVar, List
from pydantic import BaseModel
from datetime import datetime

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """
    统一API响应模型
    
    所有API接口都应返回此格式的响应，保证前后端交互的一致性
    
    Attributes:
        code: 状态码，200表示成功，其他表示业务错误
        message: 响应消息描述
        data: 响应数据（成功时包含）
        timestamp: 服务器时间戳
        request_id: 请求追踪ID（用于日志关联和问题排查）
    """
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
    timestamp: datetime = None
    request_id: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应模型
    
    用于列表查询接口的标准化分页返回
    
    Attributes:
        items: 当前页的数据列表
        total: 总记录数
        page: 当前页码（从1开始）
        page_size: 每页大小
        total_pages: 总页数
        has_next: 是否有下一页
        has_prev: 是否有上一页
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ErrorResponse(BaseModel):
    """
    错误响应模型
    
    统一的错误信息格式，便于前端统一处理错误提示
    
    Attributes:
        code: 错误码
        message: 用户友好的错误描述
        detail: 详细错误信息（开发环境显示，生产环境隐藏）
        timestamp: 错误发生时间
        request_id: 请求ID（用于排查问题）
        path: 请求路径
    """
    code: int
    message: str
    detail: Optional[str] = None
    timestamp: datetime = None
    request_id: Optional[str] = None
    path: Optional[str] = None


def success_response(data: Any = None, message: str = "success", code: int = 200) -> dict:
    """
    构建成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
        code: 状态码
        
    Returns:
        标准化的成功响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }


def error_response(code: int, message: str, detail: Optional[str] = None) -> dict:
    """
    构建错误响应
    
    Args:
        code: 错误码
        message: 用户友好的错误描述
        detail: 详细错误信息（可选）
        
    Returns:
        标准化的错误响应字典
    """
    return {
        "code": code,
        "message": message,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat()
    }


def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int
) -> dict:
    """
    构建分页响应
    
    Args:
        items: 数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页大小
        
    Returns:
        标准化的分页响应字典
    """
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }
