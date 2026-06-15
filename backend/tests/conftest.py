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
from sqlalchemy.orm import scoped_session, sessionmaker
from app.main import app
from app.core.database import Base, SessionLocal, get_db
from sqlalchemy import text


# 测试运行时产物统一放在 tests/tmp_test/ 下，已加入 .gitignore
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_TMP_TEST_DIR = os.path.join(_TESTS_DIR, "tmp_test")
os.makedirs(_TMP_TEST_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TMP_TEST_DIR}/test.db"
_TEST_DB_PATH = os.path.join(_TMP_TEST_DIR, "test.db")

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

    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


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


@pytest.fixture(scope="session")
def real_services():
    """
    真实环境服务检查
    如果 Milvus 或 DB 不可用，跳过测试
    """
    # 检查数据库
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        pytest.skip(f"数据库连接失败: {e}")

    # 检查 Milvus
    try:
        from app.services.vector_store import VectorStore
        vs = VectorStore()
        if not vs._available:
            pytest.skip("Milvus not available")
    except Exception as e:
        pytest.skip(f"Milvus连接失败: {e}")

    return {
        "db": SessionLocal(),
        "vector_store": vs,
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
