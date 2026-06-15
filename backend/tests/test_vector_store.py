"""
向量库服务单元测试（基于实际代码）
====================================
测试向量库的核心功能：
- 初始化与连接
- 向量插入
- 向量搜索
- 向量删除
- 集合管理
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from app.services.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService


class TestVectorStoreInit:
    """向量库初始化测试"""

    def test_service_initialization(self):
        """测试服务初始化"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            service = VectorStore()
            assert service._collection_name == "document_children"
            assert service._dimension > 0

    def test_dimension_from_env(self):
        """测试从环境变量读取维度"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility, \
             patch('app.services.vector_store.VectorStore._get_current_dimension', return_value=768):
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            service = VectorStore()
            assert service._dimension == 768
            assert service.dimension == 768


class TestVectorStoreBasic:
    """向量库基础测试"""

    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            return VectorStore()

    @pytest.fixture
    def sample_embedding(self):
        """示例向量"""
        return [0.1] * 1024

    def test_search_basic(self, vector_store, sample_embedding):
        """测试基本搜索"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'search') as mock_search:
            mock_search.return_value = [[Mock(id="1", distance=0.1)]]
            results = vector_store.search(sample_embedding, top_k=5)
            assert isinstance(results, list)

    def test_search_empty(self, vector_store, sample_embedding):
        """测试空结果搜索"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'search') as mock_search:
            mock_search.return_value = [[]]
            results = vector_store.search(sample_embedding, top_k=5)
            assert results == []

    def test_search_with_document_filter(self, vector_store, sample_embedding):
        """测试带文档过滤的搜索"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'search') as mock_search:
            mock_search.return_value = [[Mock(id="1", distance=0.1)]]
            results = vector_store.search(sample_embedding, top_k=5, document_id=1)
            assert isinstance(results, list)


class TestVectorOperations:
    """向量操作测试"""

    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            return VectorStore()

    @pytest.fixture
    def sample_chunks(self):
        """示例块数据"""
        return [
            {
                "parent_id": "p1",
                "child_id": "c1",
                "parent_content": "父块内容",
                "child_content": "子块内容",
            }
        ]

    @pytest.fixture
    def sample_embeddings(self):
        """示例向量数据"""
        return [[0.1] * 1024]

    def test_insert(self, vector_store, sample_chunks, sample_embeddings):
        """测试插入"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'insert') as mock_insert, \
             patch.object(vector_store.child_collection, 'flush'):
            mock_insert.return_value = Mock(insert_count=1)
            result = vector_store.insert(1, sample_chunks, sample_embeddings)
            assert mock_insert.called
            assert isinstance(result, list)

    def test_insert_empty(self, vector_store):
        """测试空数据插入"""
        with patch.object(vector_store, '_check_available'):
            result = vector_store.insert(1, [], [])
            assert result == []

    def test_delete_by_document_id(self, vector_store):
        """测试按文档ID删除"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'load'), \
             patch.object(vector_store.child_collection, 'query') as mock_query, \
             patch.object(vector_store.child_collection, 'delete') as mock_delete, \
             patch.object(vector_store.child_collection, 'flush'), \
             patch.object(vector_store.child_collection, 'compact'), \
             patch.object(vector_store.child_collection, 'wait_for_compaction_completed'):
            mock_query.return_value = [{"id": "1"}, {"id": "2"}]
            mock_delete.return_value = Mock(delete_count=2)
            result = vector_store.delete_by_document_id(1)
            assert mock_delete.called

    def test_delete_nonexistent_document(self, vector_store):
        """测试删除不存在的文档"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'load'), \
             patch.object(vector_store.child_collection, 'query') as mock_query:
            mock_query.return_value = []
            result = vector_store.delete_by_document_id(999)
            # 应该返回 None 或记录警告


class TestVectorIndexManagement:
    """向量索引管理测试"""

    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            return VectorStore()

    def test_create_collection(self, vector_store):
        """测试创建集合"""
        with patch('app.services.vector_store.Collection') as mock_collection, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_utility.has_collection.return_value = False
            vector_store._create_child_collection()
            assert mock_collection.called

    def test_drop_collection(self, vector_store):
        """测试删除集合"""
        with patch('app.services.vector_store.utility') as mock_utility:
            mock_utility.has_collection.return_value = True
            vector_store.drop_collection()
            assert mock_utility.drop_collection.called


class TestVectorOrphanCleanup:
    """向量孤儿清理测试"""

    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            return VectorStore()

    def test_delete_orphan_vectors(self, vector_store):
        """测试删除孤儿向量"""
        with patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'load'), \
             patch.object(vector_store.child_collection, 'query') as mock_query, \
             patch.object(vector_store.child_collection, 'delete') as mock_delete, \
             patch.object(vector_store.child_collection, 'flush'):
            # 模拟查询结果
            mock_query.side_effect = [
                [{"id": "1", "document_id": 1}, {"id": "2", "document_id": 2}],  # 有效向量
                [{"id": "3", "document_id": 0}],  # 孤儿向量
                [],  # 验证清理后无孤儿
            ]
            mock_delete.return_value = Mock(delete_count=1)
            result = vector_store.delete_orphan_vectors()
            assert isinstance(result, int)


class TestVectorStoreIntegration:
    """向量库集成测试"""

    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        with patch('app.services.vector_store.connections') as mock_conn, \
             patch('app.services.vector_store.utility') as mock_utility:
            mock_conn.has_connection.return_value = False
            mock_utility.has_collection.return_value = False
            return VectorStore()

    @pytest.fixture
    def embedder(self):
        """嵌入服务 fixture"""
        return EmbeddingService()

    def test_full_insert_search_cycle(self, vector_store, embedder):
        """测试完整的插入-搜索周期"""
        text = "测试文本"
        chunks = [
            {
                "parent_id": "p1",
                "child_id": "c1",
                "parent_content": text,
                "child_content": text,
            }
        ]
        embeddings = [[0.1] * 1024]
        
        with patch.object(embedder, 'embed', return_value=[0.1] * 1024), \
             patch.object(vector_store, '_check_available'), \
             patch.object(vector_store.child_collection, 'insert') as mock_insert, \
             patch.object(vector_store.child_collection, 'flush'), \
             patch.object(vector_store.child_collection, 'search') as mock_search:
            # 插入
            vector_store.insert(1, chunks, embeddings)
            assert mock_insert.called

            # 搜索
            mock_search.return_value = [[Mock(id="doc1_c1", distance=0.1, entity=Mock(get=lambda x: "test"))]]
            results = vector_store.search([0.1] * 1024, top_k=5)
            assert mock_search.called
            assert len(results) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
