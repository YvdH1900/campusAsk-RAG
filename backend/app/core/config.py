from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Campus Ask RAG"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/campus_ask"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    EMBEDDING_MODEL: str = "BAAI/bge-large-zh"
    
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    ALLOWED_ORIGINS: list = ["http://localhost:5173"]
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    
    class Config:
        env_file = ".env"


settings = Settings()
