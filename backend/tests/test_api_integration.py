"""
API 集成测试
============
测试 API 接口的完整功能：
- 对话 API（问答、会话管理）
- 文档管理 API（上传、查询、删除）
- 认证 API（注册、登录）
- 管理 API
"""

import pytest
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from app.main import app
from app.core.database import get_db, Base, engine
from app.models import User, UserRole, ChatSession, Message, Document
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="function")
def db_session():
    """数据库会话 fixture"""
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """测试客户端 fixture"""
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
def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("Test123456!"),
        role=UserRole.STUDENT,
        is_active=True,
        max_questions_per_day=100,
        questions_today=0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """创建管理员用户"""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("Admin123456!"),
        role=UserRole.ADMIN,
        is_active=True,
        # 管理员无限制，这些字段仅用于兼容性保留
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """认证头 fixture"""
    token = create_access_token({
        "sub": test_user.username,
        "role": test_user.role.value
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user):
    """管理员认证头 fixture"""
    token = create_access_token({
        "sub": admin_user.username,
        "role": admin_user.role.value
    })
    return {"Authorization": f"Bearer {token}"}


class TestChatAPI:
    """对话 API 测试"""
    
    def test_ask_question_success(self, client: TestClient, auth_headers, test_user):
        """测试成功问答"""
        question = "奖学金怎么申请？"
        
        with patch('app.services.qa_service.QAService.ask') as mock_ask:
            mock_ask.return_value = "申请奖学金需要提交申请表和成绩单。"
            
            response = client.post(
                "/api/v1/chat/ask",
                json={"question": question},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data or "message" in data
            assert len(data.get("answer", data.get("message", ""))) > 0
    
    def test_ask_question_increments_count(self, client: TestClient, auth_headers, db_session, test_user):
        """测试问答增加提问次数"""
        initial_count = test_user.questions_today
        
        with patch('app.services.qa_service.QAService.ask') as mock_ask:
            mock_ask.return_value = "测试回答"
            
            response = client.post(
                "/api/v1/chat/ask",
                json={"question": "测试问题"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            
            # 刷新用户数据
            db_session.refresh(test_user)
            assert test_user.questions_today == initial_count + 1
    
    def test_ask_question_daily_limit(self, client: TestClient, auth_headers, db_session, test_user):
        """测试每日提问限制"""
        # 设置已达到限制
        test_user.questions_today = test_user.max_questions_per_day
        db_session.commit()
        
        response = client.post(
            "/api/v1/chat/ask",
            json={"question": "测试问题"},
            headers=auth_headers
        )
        
        assert response.status_code == 429  # Too Many Requests
    
    def test_create_session(self, client: TestClient, auth_headers):
        """测试创建会话"""
        session_data = {
            "title": "测试会话"
        }
        
        response = client.post(
            "/api/v1/chat/sessions",
            json=session_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201 or response.status_code == 200
        data = response.json()
        assert "id" in data or "session_id" in data
    
    def test_get_user_sessions(self, client: TestClient, auth_headers, db_session, test_user):
        """测试获取用户会话列表"""
        # 创建测试会话
        session = ChatSession(
            user_id=test_user.id,
            title="测试会话"
        )
        db_session.add(session)
        db_session.commit()
        
        response = client.get(
            "/api/v1/chat/sessions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            assert "id" in data[0] or "session_id" in data[0]
            assert "title" in data[0]
    
    def test_get_session_messages(self, client: TestClient, auth_headers, db_session, test_user):
        """测试获取会话消息"""
        # 创建测试会话和消息
        session = ChatSession(
            user_id=test_user.id,
            title="测试会话"
        )
        db_session.add(session)
        db_session.commit()
        
        message = Message(
            session_id=session.id,
            role="user",
            content="测试消息"
        )
        db_session.add(message)
        db_session.commit()
        
        response = client.get(
            f"/api/v1/chat/sessions/{session.id}/messages",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            assert "content" in data[0]
            assert "role" in data[0]
    
    def test_submit_feedback(self, client: TestClient, auth_headers, db_session, test_user):
        """测试提交反馈"""
        # 创建测试会话和消息
        session = ChatSession(user_id=test_user.id, title="测试")
        db_session.add(session)
        db_session.commit()
        
        message = Message(session_id=session.id, role="assistant", content="测试回答")
        db_session.add(message)
        db_session.commit()
        
        feedback_data = {
            "rating": 5,
            "comment": "很好的回答"
        }
        
        response = client.post(
            f"/api/v1/chat/messages/{message.id}/feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200 or response.status_code == 201
    
    def test_ask_with_session_context(self, client: TestClient, auth_headers, db_session, test_user):
        """测试带会话上下文的问答"""
        # 创建会话
        session = ChatSession(user_id=test_user.id, title="测试会话")
        db_session.add(session)
        db_session.commit()
        
        question = "继续上一个问题"
        
        with patch('app.services.qa_service.QAService.ask') as mock_ask:
            mock_ask.return_value = "基于上下文的回答"
            
            response = client.post(
                "/api/v1/chat/ask",
                json={
                    "question": question,
                    "session_id": session.id
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            assert mock_ask.called


class TestDocumentAPI:
    """文档管理 API 测试"""
    
    def test_upload_document_success(self, client: TestClient, admin_headers, db_session, admin_user):
        """测试上传文档成功"""
        with patch('app.services.document_processor.DocumentProcessor.process_document') as mock_process:
            mock_process.return_value = {
                "document_id": 1,
                "chunks": 10,
                "status": "success"
            }
            
            # 模拟文件上传
            files = {
                "file": ("test.txt", b"测试文件内容", "text/plain")
            }
            
            response = client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=admin_headers
            )
            
            assert response.status_code == 200 or response.status_code == 201
            data = response.json()
            assert "document_id" in data or "id" in data
    
    def test_upload_document_permission(self, client: TestClient, auth_headers):
        """测试上传文档权限（学生无权上传）"""
        files = {
            "file": ("test.txt", b"测试内容", "text/plain")
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        
        # 学生应该没有上传权限
        assert response.status_code == 403
    
    def test_get_documents_list(self, client: TestClient, admin_headers, db_session, admin_user):
        """测试获取文档列表"""
        # 创建测试文档
        doc = Document(
            title="测试文档",
            file_path="/path/to/file.txt",
            uploaded_by=admin_user.id,
            status="processed"
        )
        db_session.add(doc)
        db_session.commit()
        
        response = client.get(
            "/api/v1/documents",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            assert "id" in data[0] or "document_id" in data[0]
            assert "title" in data[0]
    
    def test_delete_document(self, client: TestClient, admin_headers, db_session, admin_user):
        """测试删除文档"""
        # 创建测试文档
        doc = Document(
            title="测试文档",
            file_path="/path/to/file.txt",
            uploaded_by=admin_user.id,
            status="processed"
        )
        db_session.add(doc)
        db_session.commit()
        
        response = client.delete(
            f"/api/v1/documents/{doc.id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200 or response.status_code == 204
    
    def test_get_document_status(self, client: TestClient, admin_headers, db_session, admin_user):
        """测试获取文档状态"""
        doc = Document(
            title="测试文档",
            file_path="/path/to/file.txt",
            uploaded_by=admin_user.id,
            status="processing"
        )
        db_session.add(doc)
        db_session.commit()
        
        response = client.get(
            f"/api/v1/documents/{doc.id}/status",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestAuthAPI:
    """认证 API 测试"""
    
    def test_register_success(self, client: TestClient, db_session):
        """测试注册成功"""
        register_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "NewUser123!",
            "role": "student"
        }
        
        response = client.post(
            "/api/v1/auth/register",
            json=register_data
        )
        
        assert response.status_code == 201 or response.status_code == 200
        
        # 验证用户已创建
        user = db_session.query(User).filter(User.username == "newuser").first()
        assert user is not None
        assert user.email == "newuser@example.com"
    
    def test_register_duplicate_username(self, client: TestClient, db_session, test_user):
        """测试注册重复用户名"""
        register_data = {
            "username": test_user.username,
            "email": "another@example.com",
            "password": "Another123!",
            "role": "student"
        }
        
        response = client.post(
            "/api/v1/auth/register",
            json=register_data
        )
        
        assert response.status_code == 400  # Bad Request
    
    def test_login_success(self, client: TestClient, db_session, test_user):
        """测试登录成功"""
        login_data = {
            "username": test_user.username,
            "password": "Test123456!"
        }
        
        response = client.post(
            "/api/v1/auth/login",
            json=login_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client: TestClient, test_user):
        """测试登录密码错误"""
        login_data = {
            "username": test_user.username,
            "password": "WrongPassword123!"
        }
        
        response = client.post(
            "/api/v1/auth/login",
            json=login_data
        )
        
        assert response.status_code == 401  # Unauthorized
    
    def test_get_current_user(self, client: TestClient, auth_headers, test_user):
        """测试获取当前用户信息"""
        response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert "email" in data
        assert data["username"] == test_user.username


class TestAdminAPI:
    """管理员 API 测试"""
    
    def test_get_all_users(self, client: TestClient, admin_headers, db_session):
        """测试获取所有用户"""
        # 创建多个测试用户
        for i in range(5):
            user = User(
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password=get_password_hash("Password123!"),
                role=UserRole.STUDENT
            )
            db_session.add(user)
        db_session.commit()
        
        response = client.get(
            "/api/v1/admin/users",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5
    
    def test_update_user_role(self, client: TestClient, admin_headers, db_session):
        """测试更新用户角色"""
        user = User(
            username="testuser2",
            email="test2@example.com",
            hashed_password=get_password_hash("Password123!"),
            role=UserRole.STUDENT
        )
        db_session.add(user)
        db_session.commit()
        
        update_data = {
            "role": "teacher"
        }
        
        response = client.patch(
            f"/api/v1/admin/users/{user.id}",
            json=update_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # 验证角色已更新
        db_session.refresh(user)
        assert user.role == UserRole.TEACHER
    
    def test_deactivate_user(self, client: TestClient, admin_headers, db_session):
        """测试禁用用户"""
        user = User(
            username="testuser3",
            email="test3@example.com",
            hashed_password=get_password_hash("Password123!"),
            role=UserRole.STUDENT,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        
        response = client.patch(
            f"/api/v1/admin/users/{user.id}/deactivate",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # 验证用户已被禁用
        db_session.refresh(user)
        assert not user.is_active
    
    def test_admin_permission_check(self, client: TestClient, auth_headers):
        """测试管理员权限检查"""
        # 学生用户尝试访问管理员接口
        response = client.get(
            "/api/v1/admin/users",
            headers=auth_headers
        )
        
        assert response.status_code == 403  # Forbidden


class TestAPIPerformance:
    """API 性能测试"""
    
    def test_ask_response_time(self, client: TestClient, auth_headers):
        """测试问答响应时间"""
        with patch('app.services.qa_service.QAService.ask') as mock_ask:
            mock_ask.return_value = "测试回答"
            
            start_time = time.time()
            
            response = client.post(
                "/api/v1/chat/ask",
                json={"question": "测试问题"},
                headers=auth_headers
            )
            
            elapsed = time.time() - start_time
            
            assert response.status_code == 200
            assert elapsed < 5.0, "响应时间应小于 5 秒"
    
    def test_concurrent_requests(self, client: TestClient, auth_headers):
        """测试并发请求处理"""
        import concurrent.futures
        
        def make_request():
            with patch('app.services.qa_service.QAService.ask') as mock_ask:
                mock_ask.return_value = "测试回答"
                
                response = client.post(
                    "/api/v1/chat/ask",
                    json={"question": "测试问题"},
                    headers=auth_headers
                )
                return response.status_code
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in futures]
        
        # 所有请求都应该成功
        assert all(r == 200 for r in results)
    
    def test_large_payload_handling(self, client: TestClient, auth_headers):
        """测试大负载处理"""
        large_question = "测试问题" * 100
        
        with patch('app.services.qa_service.QAService.ask') as mock_ask:
            mock_ask.return_value = "测试回答"
            
            response = client.post(
                "/api/v1/chat/ask",
                json={"question": large_question},
                headers=auth_headers
            )
            
            assert response.status_code == 200 or response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
