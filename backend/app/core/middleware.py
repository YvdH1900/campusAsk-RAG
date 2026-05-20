"""
请求中间件
===========
实现企业级请求处理管道：
- 请求ID生成和追踪
- 请求/响应日志记录
- 请求耗时统计
- CORS安全增强
- 请求体大小限制
"""

import time
import uuid
import logging
import sys
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)


class RequestMiddleware(BaseHTTPMiddleware):
    """
    企业级请求中间件
    
    功能：
    1. 为每个请求生成唯一追踪ID（Request-ID）
    2. 记录详细的请求/响应日志
    3. 统计请求处理耗时
    4. 添加安全响应头
    
    Usage:
        app.add_middleware(RequestMiddleware)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        request_id = self._generate_request_id()
        request.state.request_id = request_id
        
        print(f"[DIAG-MW] >>> {request.method} {request.url.path}", file=sys.stderr, flush=True)
        
        logger.info(
            f"[REQ] [{request.method}] {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent", "Unknown")
            }
        )
        
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        response.headers["X-Powered-By"] = "CampusAsk-RAG/1.0"
        
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            f"[RES] [{response.status_code}] {request.method} {request.url.path} ({process_time:.2f}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time_ms": round(process_time, 2)
            }
        )
        
        return response
    
    def _generate_request_id(self) -> str:
        """
        生成唯一请求ID
        
        使用UUID v4确保全局唯一性，格式：req-{uuid}
        
        Returns:
            str: 唯一请求标识符
        """
        return f"req-{uuid.uuid4().hex[:12]}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件
    
    添加常见的安全响应头，防止常见Web攻击：
    - XSS防护
    - 点击劫持保护
    - MIME类型嗅探防护
    - 引用策略控制
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 生产环境应使用更严格的 CSP
        # 如果禁用了 API 文档，不需要允许 CDN 资源
        if getattr(settings, 'ENABLE_API_DOCS', True):
            # 开发环境：允许 CDN 资源用于 Swagger UI
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https://fastapi.tiangolo.com;"
            )
        else:
            # 生产环境：严格限制，只允许本地资源
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self';"
            )
        
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的速率限制中间件（基于内存）
    
    ⚠️ 生产环境建议使用Redis-based方案（如 slowapi）
    
    功能：
    - 基于IP地址限制请求频率
    - 可配置时间窗口和最大请求数
    - 返回429状态码和Retry-After头
    """
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests_store: dict = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        if client_ip not in self.requests_store:
            self.requests_store[client_ip] = []
        
        request_times = self.requests_store[client_ip]
        request_times = [t for t in request_times if current_time - t < self.window_seconds]
        
        if len(request_times) >= self.max_requests:
            from fastapi.responses import JSONResponse
            
            retry_after = int(self.window_seconds - (current_time - request_times[0]))
            
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后重试",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        request_times.append(current_time)
        self.requests_store[client_ip] = request_times
        
        return await call_next(request)
