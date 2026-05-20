"""
权限过滤服务
============
基于用户角色过滤检索结果
支持：
- 学生只能看到公开文档
- 教师可以看到内部文档
- 管理员可以看到所有文档
"""

import logging
from typing import List, Dict
from app.models import UserRole

logger = logging.getLogger(__name__)


class PermissionFilter:
    """权限过滤器"""

    def filter_by_role(
        self,
        results: List[Dict],
        user_role: str,
    ) -> List[Dict]:
        """
        根据用户角色过滤检索结果
        
        Args:
            results: 检索结果列表
            user_role: 用户角色 (student/teacher/admin)
            
        Returns:
            过滤后的结果
        """
        if not results:
            return []

        # 管理员可以看到所有文档
        if user_role == UserRole.ADMIN:
            return results

        filtered = []
        for result in results:
            visibility = result.get("visibility", "public")
            
            if user_role == UserRole.STUDENT:
                # 学生只能看到公开文档
                if visibility == "public":
                    filtered.append(result)
            
            elif user_role == UserRole.TEACHER:
                # 教师可以看到公开和内部文档
                if visibility in ["public", "internal"]:
                    filtered.append(result)

        logger.info(
            f"权限过滤: {user_role} - {len(results)} -> {len(filtered)} 条结果"
        )
        return filtered


# 全局实例
permission_filter = PermissionFilter()
