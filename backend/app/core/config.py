"""
应用配置模块
=============
负责管理整个应用的所有配置项，支持从环境变量或.env文件读取配置。
使用 pydantic-settings 实现类型安全的配置管理。
"""

from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    应用配置类
    
    继承自 BaseSettings，自动从环境变量或 .env 文件读取配置。
    所有配置项都有默认值，方便开发环境使用。
    生产环境应通过环境变量覆盖敏感配置。
    """
    
    # ==================== 基础配置 ====================
    PROJECT_NAME: str = "Campus Ask RAG"
    VERSION: str = "0.1.0"
    
    # ==================== 数据库配置 ====================
    MYSQL_USER: str = "root"
    MYSQL_ROOT_PASSWORD: str = "root"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "campus_ask_rag"
    
    # 由组件自动拼接，无需在 .env 中手动设置
    # 如果要覆盖（如 Docker Compose 动态注入），可设置环境变量 DATABASE_URL
    DATABASE_URL: str = ""
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ==================== Celery 配置 ====================
    # Celery Broker URL（使用 RabbitMQ）
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"

    # Celery Backend URL（使用 Redis）
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Celery 任务结果过期时间（秒），默认 1 小时
    CELERY_RESULT_EXPIRES: int = 3600
    
    # Celery 任务重试最大次数
    CELERY_TASK_MAX_RETRIES: int = 3
    
    # Celery 任务重试间隔（秒）
    CELERY_TASK_RETRY_DELAY: int = 60
    
    # ==================== 缓存配置 ====================
    # Redis 缓存 TTL（秒），默认 1 小时
    CACHE_TTL: int = 3600
    
    # ==================== 向量数据库配置 ====================
    # Milvus 向量数据库主机地址
    MILVUS_HOST: str = "localhost"
    
    # Milvus 向量数据库端口
    MILVUS_PORT: int = 19530
    
    # ==================== LLM 配置 ====================
    # 通义千问 API 密钥
    # pydantic-settings 会自动从环境变量和 .env 文件读取
    DASHSCOPE_API_KEY: str = ""
    
    # 使用的 LLM 模型名称
    # 使用通义千问模型，可选: qwen-turbo, qwen-plus, qwen-max
    LLM_MODEL: str = "qwen-plus"
    
    # 文本向量化 Embedding 模型
    # 使用通义千问的 Embedding 模型
    # text-embedding-v3 是阿里云百炼平台提供的高质量 Embedding 模型
    EMBEDDING_MODEL: str = "text-embedding-v3"
    
    # ==================== 重排序模型配置 ====================
    # 重排序模型名称（阿里云百炼平台 API 模型）
    # 使用阿里云的 Reranker API，无需本地模型
    # 推荐: gte-rerank（阿里云百炼平台提供的高质量重排序模型）
    RERANKER_MODEL: str = "gte-rerank"
    
    # ==================== 安全配置 ====================
    # JWT Token 加密密钥
    # ⚠️ 生产环境必须通过环境变量设置为强随机字符串
    # 开发环境可使用默认值（仅用于本地调试）
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    
    # Access Token 过期时间（分钟），默认 7 天
    # 60 分钟 * 24 小时 * 7 天
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # 密码重置 Token 过期时间（分钟），默认 30 分钟
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 默认管理员密码（可选，如果不设置将自动生成随机密码）
    DEFAULT_ADMIN_PASSWORD: Optional[str] = None
    
    # ==================== 服务器配置 ====================
    # 允许跨域请求的来源地址（前端开发服务器地址）
    ALLOWED_ORIGINS: list = ["http://localhost:5173"]
    
    # ==================== API 文档配置 ====================
    # 是否启用 API 文档（Swagger UI 和 ReDoc）
    # ⚠️ 生产环境建议设置为 False 以避免 API 接口暴露
    # 开发环境设置为 True 方便调试
    ENABLE_API_DOCS: bool = True
    
    class Config:
        """
        Pydantic 配置类
        
        env_file: 指定从 .env 文件读取配置
        系统环境变量优先级高于 .env 文件
        """
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    @model_validator(mode='after')
    def build_database_url(self):
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_ROOT_PASSWORD}"
                f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
                f"?charset=utf8mb4"
            )
        return self


# 创建全局配置实例
# 其他模块通过 from app.core.config import settings 导入使用
settings = Settings()
