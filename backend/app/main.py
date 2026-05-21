"""
FastAPI 应用入口模块
==================================
创建并配置 FastAPI 应用实例，集成：
- 全局异常处理
- 请求追踪中间件
- 结构化日志
- 安全响应头
- CORS配置
- 健康检查和监控端点
- API版本控制

这是后端服务的启动入口。
"""

import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from app.core.config import settings
from app.core.response import success_response, error_response
from app.core.exceptions import BaseAppException, ConfigurationException
from app.core.exception_handlers import global_exception_handler
from app.core.middleware import RequestMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware
from app.core.logging_config import setup_logging, get_logger
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.admin import router as admin_router
from app.api.chat import router as chat_router


logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时：
    - 初始化日志系统
    - 检查必要配置
    - 验证数据库连接
    - 预热缓存和连接池
    
    关闭时：
    - 关闭数据库连接
    - 清理资源
    - 保存状态
    """
    logger.info("🚀 CampusAsk-RAG 正在启动...")
    
    setup_logging(
        level=getattr(settings, 'LOG_LEVEL', 'INFO'),
        log_file=str(LOG_DIR / 'app.log'),
        json_format=False
    )
    
    _validate_configuration()
    
    _check_database_connection()
    
    _ensure_tables_exist()
    
    _create_default_admin_if_not_exists()
    
    _sync_model_config_from_db()
    
    logger.info("✅ 系统初始化完成")
    
    yield
    
    logger.info("👋 CampusAsk-RAG 正在关闭...")


def _validate_configuration():
    """
    验证关键配置项
    
    检查必要的密钥和连接信息是否已配置
    
    Raises:
        ConfigurationException: 缺少必要配置
    """
    if not settings.DASHSCOPE_API_KEY or settings.DASHSCOPE_API_KEY == 'sk-your-api-key-here':
        logger.warning("⚠️ 未配置通义千问API密钥，AI问答功能将不可用")
    
    if not settings.SECRET_KEY or 'change-in-production' in settings.SECRET_KEY:
        logger.warning("⚠️ 使用默认JWT密钥，生产环境请更换！")


def _check_database_connection():
    """
    测试数据库连接（可选，失败时警告但不阻止启动）
    """
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        logger.info("✅ 数据库连接成功")
        
    except Exception as e:
        logger.warning(f"⚠️ 数据库连接失败（将以降级模式启动）: {str(e)}")
        logger.warning("💡 提示：请检查 MySQL 服务是否运行，以及 .env 中的 DATABASE_URL 配置是否正确")


def _ensure_tables_exist():
    """
    确保所有数据库表已创建
    导入所有模型后调用 create_all，避免遗漏新表
    """
    try:
        from app.core.database import engine
        from app.models import Base  # 导入 Base 会触发所有模型注册
        
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表检查完成")
        
    except Exception as e:
        logger.warning(f"⚠️ 数据库表创建失败（可能已存在）: {str(e)}")


def _create_default_admin_if_not_exists():
    """
    检查并创建默认管理员账号（如果不存在）
    """
    try:
        from app.core.database import SessionLocal
        from app.models import User, UserRole
        from app.core.security import get_password_hash
        import os
        
        db = SessionLocal()
        try:
            # 检查是否已存在管理员
            admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
            
            if admin:
                logger.info("✅ 管理员账号已存在")
                return
            
            # 创建管理员账号
            admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD") or getattr(settings, 'DEFAULT_ADMIN_PASSWORD', None)
            
            if not admin_password:
                import secrets
                admin_password = secrets.token_urlsafe(12)
                logger.warning(f"⚠️ 未配置默认管理员密码，已自动生成随机密码，请妥善保管！")
            
            hashed_password = get_password_hash(admin_password)
            
            new_admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                is_active=True,
                # 管理员无限制，这些字段仅用于兼容性保留
            )
            
            db.add(new_admin)
            db.commit()
            
            logger.info(f"✅ 已创建默认管理员账号")
            logger.info(f"   用户名：admin")
            logger.warning(f"   ⚠️  请查看启动日志中的随机密码，并立即登录修改！")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ 创建管理员账号失败：{str(e)}")
        logger.warning("💡 提示：请检查数据库表是否已创建")


def _sync_model_config_from_db():
    """
    启动时从数据库同步模型配置到环境变量
    确保重启后使用数据库中已激活的模型，而不是配置文件的默认值
    """
    try:
        from app.core.database import SessionLocal
        from app.models import ModelConfig
        
        db = SessionLocal()
        try:
            # 获取激活的 LLM 模型
            active_llm = db.query(ModelConfig).filter(
                ModelConfig.model_type == "llm",
                ModelConfig.is_active == True
            ).first()
            
            if active_llm:
                os.environ["DASHSCOPE_API_KEY"] = active_llm.api_key
                os.environ["LLM_MODEL"] = active_llm.model_name
                logger.info(f"✅ 从数据库加载 LLM 模型: {active_llm.model_name}")
            else:
                logger.info("⚠️ 数据库无激活的 LLM 模型，使用配置文件默认值")
            
            # 获取激活的 Embedding 模型
            active_embedding = db.query(ModelConfig).filter(
                ModelConfig.model_type == "embedding",
                ModelConfig.is_active == True
            ).first()
            
            if active_embedding:
                os.environ["EMBEDDING_MODEL"] = active_embedding.model_name
                if active_embedding.dimension:
                    os.environ["EMBEDDING_DIMENSION"] = str(active_embedding.dimension)
                logger.info(f"✅ 从数据库加载 Embedding 模型: {active_embedding.model_name} (维度: {active_embedding.dimension})")
            else:
                logger.info("⚠️ 数据库无激活的 Embedding 模型，使用配置文件默认值")
                
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"从数据库加载模型配置失败: {e}，使用配置文件默认值")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    ## 🎓 CampusAsk-RAG 校园知识库智能问答系统
    
    ### 功能特性
    - 🔍 **RAG 智能问答**：基于校园知识库的精准回答
    - 📄 **文档管理**：支持 PDF/Word/TXT 文档上传和处理
    -  **多角色权限**：学生、教师、管理员三级权限体系
    - 💬 **对话历史**：完整的会话记录和管理
    - 🛡️ **企业级安全**：JWT 认证、Rate Limiting、输入校验
    
    ### 技术栈
    - **后端**: FastAPI + SQLAlchemy + MySQL
    - **AI 引擎**: 通义千问 LLM + Milvus 向量库
    - **前端**: Vue 3 + Element Plus + TypeScript
    """,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time", "Content-Disposition", "Content-Length"],
)

app.add_middleware(RequestMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

if getattr(settings, 'ENABLE_RATE_LIMIT', True):
    app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

app.add_exception_handler(Exception, global_exception_handler)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


@app.get("/health", tags=["系统"])
@app.get("/api/health", tags=["系统"], include_in_schema=False)
async def health_check():
    """
    健康检查接口
    
    用于监控服务运行状态，返回详细的系统健康信息。
    负载均衡器、容器编排系统和监控系统定期调用此接口。
    
    Returns:
        dict: 包含服务状态、版本号、时间戳等信息
        
    Example Response:
        ```json
        {
            "status": "healthy",
            "version": "0.1.0",
            "timestamp": "2024-01-01T12:00:00Z",
            "services": {
                "database": "connected",
                "redis": "connected",
                "milvus": "unknown"
            }
        }
        ```
    """
    services_status = {}
    
    try:
        from app.core.database import engine
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text("SELECT 1"))
        services_status["database"] = "connected"
    except Exception as e:
        services_status["database"] = f"error: {str(e)}"
    
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        services_status["redis"] = "connected"
    except Exception as e:
        services_status["redis"] = f"error: {str(e)}"
    
    try:
        from pymilvus import connections, utility
        if connections.has_connection("default"):
            utility.list_collections()
            services_status["milvus"] = "connected"
        else:
            services_status["milvus"] = "not_configured"
    except Exception as e:
        services_status["milvus"] = f"error: {str(e)}"
    
    all_healthy = all(
        status == "connected" 
        for status in services_status.values()
    )
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": settings.VERSION,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        "services": services_status
    }


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    """
    Swagger UI 文档页面（使用本地资源）
    
    使用 FastAPI 内置的 Swagger UI 资源，避免 CDN 依赖
    
    ⚠️ 生产环境应禁用此接口以防止 API 接口暴露
    """
    if not getattr(settings, 'ENABLE_API_DOCS', True):
        return JSONResponse(
            status_code=403,
            content={"code": 403, "message": "API 文档已禁用"}
        )
    
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.PROJECT_NAME} - API 文档",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui():
    """
    ReDoc 文档页面（使用本地资源）
    
    使用 FastAPI 内置的 ReDoc 资源，避免 CDN 依赖
    
    ⚠️ 生产环境应禁用此接口以防止 API 接口暴露
    """
    if not getattr(settings, 'ENABLE_API_DOCS', True):
        return JSONResponse(
            status_code=403,
            content={"code": 403, "message": "API 文档已禁用"}
        )
    
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{settings.PROJECT_NAME} - API 文档",
    )


@app.get("/api/info", tags=["系统"])
async def api_info():
    """
    API 信息接口
    
    返回 API 的元数据信息，包括版本、支持的功能列表等。
    
    Returns:
        dict: API 基本信息
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": "CampusAsk-RAG 校园知识库智能问答系统 API",
        "endpoints": {
            "auth": "/api/v1/auth/*",
            "chat": "/api/v1/chat/*",
            "documents": "/api/v1/documents/*",
            "admin": "/api/v1/admin/*"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


@app.get("/", tags=["系统"])
async def root():
    """
    根路径接口
    
    返回欢迎信息和基本导航链接。
    
    Returns:
        dict: 欢迎信息和链接
    """
    return {
        "message": "Welcome to CampusAsk-RAG API",
        "version": settings.VERSION,
        "documentation": "/docs",
        "health_check": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
