"""
Pytest 配置文件
===============
全局测试fixture和配置
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)


@pytest.fixture(scope="session")
def db_engine():
    """
    会话级数据库引擎
    
    整个测试会话只创建一次引擎
    """
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    Base.metadata.drop_all(bind=engine)
    
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    函数级数据库会话
    
    每个测试函数使用独立的数据库会话
    测试结束后自动回滚
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    测试客户端fixture
    
    使用测试数据库会话覆盖生产依赖
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    test_client = TestClient(app)
    
    yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient, username: str = "testuser"):
    """
    认证头fixture
    
    生成有效的JWT Token并返回认证头字典
    """
    from app.core.security import create_access_token
    
    token = create_access_token({"sub": username, "role": "student"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_user_data():
    """示例用户数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPassword123!",
        "role": "student"
    }


@pytest.fixture
def admin_headers():
    """管理员认证头"""
    from app.core.security import create_access_token
    
    token = create_access_token({
        "sub": "admin", 
        "role": "admin"
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def teacher_headers():
    """教师认证头"""
    from app.core.security import create_access_token
    
    token = create_access_token({
        "sub": "teacher", 
        "role": "teacher"
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_check(client: TestClient):
    """健康检查接口测试"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
