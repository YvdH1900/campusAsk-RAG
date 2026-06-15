"""
权限过滤服务测试
===============
测试学生/教师/管理员三级权限过滤逻辑
"""

import pytest
from app.services.permission_filter import PermissionFilter
from app.models import UserRole


class TestPermissionFilter:
    """权限过滤测试"""

    @pytest.fixture
    def filter_service(self):
        return PermissionFilter()

    @pytest.fixture
    def mixed_results(self):
        """混合可见性的检索结果"""
        return [
            {"id": 1, "content": "公开文档1", "visibility": "public"},
            {"id": 2, "content": "内部文档1", "visibility": "internal"},
            {"id": 3, "content": "公开文档2", "visibility": "public"},
            {"id": 4, "content": "机密文档1", "visibility": "confidential"},
            {"id": 5, "content": "内部文档2", "visibility": "internal"},
        ]

    def test_student_sees_only_public(self, filter_service, mixed_results):
        """学生只能看到公开文档"""
        filtered = filter_service.filter_by_role(mixed_results, UserRole.STUDENT)
        assert len(filtered) == 2
        assert all(r["visibility"] == "public" for r in filtered)
        assert {r["id"] for r in filtered} == {1, 3}

    def test_teacher_sees_public_and_internal(self, filter_service, mixed_results):
        """教师可以看到公开和内部文档"""
        filtered = filter_service.filter_by_role(mixed_results, UserRole.TEACHER)
        assert len(filtered) == 4
        assert all(r["visibility"] in ("public", "internal") for r in filtered)
        assert {r["id"] for r in filtered} == {1, 2, 3, 5}

    def test_admin_sees_all(self, filter_service, mixed_results):
        """管理员可以看到所有文档"""
        filtered = filter_service.filter_by_role(mixed_results, UserRole.ADMIN)
        assert len(filtered) == 5
        assert filtered == mixed_results

    def test_empty_results(self, filter_service):
        """空结果返回空列表"""
        assert filter_service.filter_by_role([], UserRole.STUDENT) == []

    def test_missing_visibility_field(self, filter_service):
        """缺少 visibility 字段时默认为 public"""
        results = [{"id": 1, "content": "无 visibility 字段"}]
        filtered = filter_service.filter_by_role(results, UserRole.STUDENT)
        assert len(filtered) == 1

    def test_unknown_visibility(self, filter_service):
        """未知 visibility 值被过滤掉"""
        results = [
            {"id": 1, "content": "未知可见性", "visibility": "unknown"},
            {"id": 2, "content": "公开", "visibility": "public"},
        ]
        filtered = filter_service.filter_by_role(results, UserRole.STUDENT)
        assert len(filtered) == 1
        assert filtered[0]["id"] == 2

    def test_unknown_role(self, filter_service, mixed_results):
        """未知角色返回空列表"""
        filtered = filter_service.filter_by_role(mixed_results, "unknown_role")
        assert filtered == []

    def test_all_public(self, filter_service):
        """全部公开文档对所有角色可见"""
        results = [
            {"id": 1, "content": "公开1", "visibility": "public"},
            {"id": 2, "content": "公开2", "visibility": "public"},
        ]
        for role in [UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN]:
            filtered = filter_service.filter_by_role(results, role)
            assert len(filtered) == 2

    def test_all_confidential(self, filter_service):
        """全部机密文档只有管理员可见"""
        results = [
            {"id": 1, "content": "机密1", "visibility": "confidential"},
            {"id": 2, "content": "机密2", "visibility": "confidential"},
        ]
        assert filter_service.filter_by_role(results, UserRole.STUDENT) == []
        assert filter_service.filter_by_role(results, UserRole.TEACHER) == []
        assert len(filter_service.filter_by_role(results, UserRole.ADMIN)) == 2
