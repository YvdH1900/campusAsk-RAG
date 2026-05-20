"""
单元测试：认证API
=================
测试用户注册、登录、Token验证等核心功能
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    decode_token
)
from app.models import User, UserRole


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """测试数据库会话覆盖"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db_session():
    """
    测试数据库会话fixture
    
    每个测试前创建新表，测试后清理数据
    """
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    yield session
    
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("Test123456!"),
        role=UserRole.STUDENT,
        is_active=True,
        max_questions_per_day=100,
        max_uploads_per_day=0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """创建管理员用户"""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("Admin123456!"),
        role=UserRole.ADMIN,
        is_active=True,
        # 管理员无限制，这些字段仅用于兼容性保留
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


class TestPasswordSecurity:
    """密码安全测试"""
    
    def test_password_hashing(self):
        """测试密码哈希"""
        password = "MySecurePassword123!"
        
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50
        
        assert verify_password(password, hashed)
        assert not verify_password("wrongpassword", hashed)
    
    def test_password_hash_uniqueness(self):
        """相同密码应生成不同哈希（加盐）"""
        password = "SamePassword123"
        
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestTokenManagement:
    """Token管理测试"""
    
    def test_create_token(self):
        """创建访问令牌"""
        user_data = {
            "sub": "testuser",
            "role": "student",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24)
        }
        
        token = create_access_token(user_data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 100
    
    def test_decode_valid_token(self):
        """解码有效Token"""
        token = create_access_token(
            {"sub": "testuser", "role": "student"},
            expires_delta=timedelta(hours=1)
        )
        
        payload = decode_token(token)
        
        assert payload is not None
        assert payload.get("sub") == "testuser"
        assert payload.get("role") == "student"
    
    def test_decode_expired_token(self):
        """解码过期Token"""
        token = create_access_token(
            {"sub": "testuser"},
            expires_delta=timedelta(seconds=-1)
        )
        
        payload = decode_token(token)
        
        assert payload is None
    
    def test_decode_invalid_token(self):
        """解码无效Token"""
        invalid_tokens = [
            "",
            "invalid.token.here",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
        ]
        
        for token in invalid_tokens:
            payload = decode_token(token)
            assert payload is None


class TestUserRegistration:
    """用户注册测试"""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client: TestClient, db_session):
        """成功注册"""
        response = client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "NewUser123!",
            "role": "student"
        })
        
        assert response.status_code == 201 or response.status_code == 200
        
        user = db_session.query(User).filter(User.username == "newuser").first()
        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.role == UserRole.STUDENT
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: TestClient, test_user):
        """重复用户名注册失败"""
        response = client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "another@example.com",
            "password": "Password123!",
            "role": "student"
        })
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: TestClient):
        """弱密码注册失败"""
        response = client.post("/api/v1/auth/register", json={
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "123",
            "role": "student"
        })
        
        assert response.status_code == 422 or response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: TestClient):
        """无效邮箱格式"""
        response = client.post("/api/v1/auth/register", json={
            "username": "emailuser",
            "email": "not-an-email",
            "password": "ValidPass123!",
            "role": "student"
        })
        
        assert response.status_code == 422 or response.status_code == 400


class TestUserLogin:
    """用户登录测试"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: TestClient, test_user):
        """成功登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "Test123456!"
        })
        
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: TestClient, test_user):
        """错误密码登录失败"""
        response = client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "WrongPassword!"
        })
        
        assert response.status_code == 401 or response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: TestClient):
        """不存在的用户登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "SomePassword!"
        })
        
        assert response.status_code == 401 or response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: TestClient, db_session):
        """禁用用户登录失败"""
        inactive_user = User(
            username="inactive",
            email="inactive@test.com",
            hashed_password=get_password_hash("Test123456!"),
            role=UserRole.STUDENT,
            is_active=False
        )
        db_session.add(inactive_user)
        db_session.commit()
        
        response = client.post("/api/v1/auth/login", json={
            "username": "inactive",
            "password": "Test123456!"
        })
        
        assert response.status_code == 403 or response.status_code == 401


class TestProtectedEndpoints:
    """受保护端点测试"""
    
    def get_auth_header(self, username: str = "testuser") -> dict:
        """获取认证头"""
        token = create_access_token({"sub": username, "role": "student"})
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, client: TestClient):
        """无Token访问受保护端点"""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401 or response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """无效Token访问"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401 or response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: TestClient, test_user):
        """获取当前用户信息"""
        response = client.get(
            "/api/v1/auth/me",
            headers=self.get_auth_header(test_user.username)
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert "hashed_password" not in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
