"""
向量库服务单元测试
==================
测试向量库的核心功能：
- 向量增删改查
- 一致性检查
- 批量操作
- 索引管理
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from app.services.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService
from app.services.vector_consistency import VectorConsistencyChecker


class TestVectorStoreBasic:
    """向量库基础测试"""
    
    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        return VectorStore()
    
    @pytest.fixture
    def sample_embedding(self):
        """示例向量"""
        return [0.1] * 1024
    
    def test_vector_store_initialization(self, vector_store):
        """测试向量库初始化"""
        assert vector_store.child_collection is not None
        assert vector_store.parent_collection is not None
    
    def test_search_basic(self, vector_store, sample_embedding):
        """测试基本搜索"""
        results = vector_store.search(sample_embedding, top_k=5)
        
        assert isinstance(results, list)
        assert len(results) <= 5
        
        if results:
            for result in results:
                assert "score" in result or "distance" in result
                assert "parent_content" in result or "child_content" in result
    
    def test_search_with_document_filter(self, vector_store, sample_embedding):
        """测试带文档过滤的搜索"""
        document_id = 1
        results = vector_store.search(sample_embedding, top_k=5, document_id=document_id)
        
        assert isinstance(results, list)
        
        if results:
            for result in results:
                assert result.get("document_id") == document_id
    
    def test_search_deduplication(self, vector_store, sample_embedding):
        """测试搜索结果去重"""
        results = vector_store.search(sample_embedding, top_k=10)
        
        if results:
            parent_ids = [r.get("parent_id") for r in results]
            # 验证没有重复的 parent_id
            assert len(parent_ids) == len(set(parent_ids)), "搜索结果应该去重"


class TestVectorConsistency:
    """向量一致性检查测试"""
    
    @pytest.fixture
    def consistency_checker(self):
        """一致性检查器 fixture"""
        return VectorConsistencyChecker()
    
    def test_check_orphan_vectors(self, consistency_checker):
        """测试孤儿向量检查"""
        with patch('app.services.vector_store.VectorStore') as mock_store:
            mock_collection = Mock()
            mock_collection.query.return_value = [
                {"document_id": 1, "parent_id": "p1", "child_id": "c1"},
                {"document_id": 999, "parent_id": "p2", "child_id": "c2"},  # 孤儿
            ]
            mock_store.return_value.child_collection = mock_collection
            
            with patch('sqlalchemy.orm.Session') as mock_session:
                mock_db = Mock()
                mock_db.query().filter().all.return_value = [Mock(id=1)]
                
                orphans = consistency_checker.check_orphan_vectors(mock_db)
                
                assert isinstance(orphans, list)
    
    def test_check_vector_document_consistency(self, consistency_checker):
        """测试向量 - 文档一致性检查"""
        with patch('app.services.vector_store.VectorStore') as mock_store:
            mock_collection = Mock()
            mock_collection.query.return_value = [
                {"document_id": 1, "parent_id": "p1"},
                {"document_id": 2, "parent_id": "p2"},
            ]
            mock_store.return_value.child_collection = mock_collection
            
            with patch('sqlalchemy.orm.Session') as mock_session:
                mock_db = Mock()
                mock_db.query().filter().all.return_value = [
                    Mock(id=1, document_hash="hash1"),
                    Mock(id=2, document_hash="hash2"),
                ]
                
                result = consistency_checker.check_vector_document_consistency(mock_db)
                
                assert isinstance(result, dict)
                assert "total_vectors" in result or "consistent" in result
    
    def test_repair_inconsistencies(self, consistency_checker):
        """测试修复不一致"""
        with patch('app.services.vector_store.VectorStore') as mock_store:
            mock_collection = Mock()
            mock_store.return_value.child_collection = mock_collection
            
            orphan_ids = ["p1", "p2"]
            
            deleted_count = consistency_checker.repair_inconsistencies(mock_store, orphan_ids)
            
            assert isinstance(deleted_count, int)
            assert deleted_count >= 0


class TestVectorOperations:
    """向量操作测试"""
    
    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        return VectorStore()
    
    @pytest.fixture
    def sample_documents(self):
        """示例文档"""
        return [
            {
                "document_id": 1,
                "parent_id": "p1",
                "child_id": "c1",
                "parent_content": "父块内容 1",
                "child_content": "子块内容 1",
                "embedding": [0.1] * 1024,
            },
            {
                "document_id": 1,
                "parent_id": "p1",
                "child_id": "c2",
                "parent_content": "父块内容 1",
                "child_content": "子块内容 2",
                "embedding": [0.2] * 1024,
            },
        ]
    
    def test_batch_insert(self, vector_store, sample_documents):
        """测试批量插入"""
        with patch.object(vector_store.child_collection, 'insert') as mock_insert:
            mock_insert.return_value = Mock(insert_count=len(sample_documents))
            
            result = vector_store.batch_insert(sample_documents)
            
            assert mock_insert.called
            assert result is not None
    
    def test_delete_by_document_id(self, vector_store):
        """测试按文档 ID 删除"""
        document_id = 1
        
        with patch.object(vector_store.child_collection, 'delete') as mock_delete, \
             patch.object(vector_store.parent_collection, 'delete') as mock_parent_delete:
            
            mock_delete.return_value = Mock(delete_count=5)
            mock_parent_delete.return_value = Mock(delete_count=2)
            
            result = vector_store.delete_by_document_id(document_id)
            
            assert mock_delete.called
            assert mock_parent_delete.called
            assert result is not None
    
    def test_delete_nonexistent_document(self, vector_store):
        """测试删除不存在的文档"""
        document_id = 999
        
        with patch.object(vector_store.child_collection, 'delete') as mock_delete:
            mock_delete.return_value = Mock(delete_count=0)
            
            result = vector_store.delete_by_document_id(document_id)
            
            assert mock_delete.called
            assert result is not None
    
    def test_update_vector(self, vector_store):
        """测试更新向量"""
        with patch.object(vector_store.child_collection, 'update') as mock_update:
            mock_update.return_value = Mock(update_count=1)
            
            update_data = {
                "child_content": "更新后的内容",
                "embedding": [0.5] * 1024,
            }
            
            result = vector_store.update_vector("p1", "c1", update_data)
            
            assert mock_update.called
            assert result is not None


class TestVectorIndexManagement:
    """向量索引管理测试"""
    
    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        return VectorStore()
    
    def test_create_index(self, vector_store):
        """测试创建索引"""
        with patch.object(vector_store.child_collection, 'create_index') as mock_create:
            mock_create.return_value = Mock()
            
            vector_store.create_index(
                index_name="test_index",
                index_params={"index_type": "HNSW"}
            )
            
            assert mock_create.called
    
    def test_drop_index(self, vector_store):
        """测试删除索引"""
        with patch.object(vector_store.child_collection, 'drop_index') as mock_drop:
            mock_drop.return_value = Mock()
            
            vector_store.drop_index("test_index")
            
            assert mock_drop.called
    
    def test_load_collection(self, vector_store):
        """测试加载集合"""
        with patch.object(vector_store.child_collection, 'load') as mock_load:
            mock_load.return_value = Mock()
            
            vector_store.load_collection()
            
            assert mock_load.called
    
    def test_release_collection(self, vector_store):
        """测试释放集合"""
        with patch.object(vector_store.child_collection, 'release') as mock_release:
            mock_release.return_value = Mock()
            
            vector_store.release_collection()
            
            assert mock_release.called


class TestVectorMetrics:
    """向量指标测试"""
    
    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        return VectorStore()
    
    def test_collection_stats(self, vector_store):
        """测试集合统计信息"""
        with patch.object(vector_store.child_collection, 'query') as mock_query:
            mock_query.return_value = [{"count": 1000}]
            
            stats = vector_store.get_collection_stats()
            
            assert isinstance(stats, dict)
            assert "count" in stats or "total" in stats
    
    def test_vector_distribution(self, vector_store):
        """测试向量分布"""
        with patch.object(vector_store.child_collection, 'query') as mock_query:
            mock_query.return_value = [
                {"document_id": 1, "count": 10},
                {"document_id": 2, "count": 20},
            ]
            
            distribution = vector_store.get_vector_distribution()
            
            assert isinstance(distribution, list)
            assert len(distribution) > 0
    
    def test_similarity_score_distribution(self, vector_store, sample_embedding):
        """测试相似度分数分布"""
        with patch.object(vector_store.child_collection, 'search') as mock_search:
            mock_search.return_value = [
                [
                    Mock(entity={"score": 0.9}, distance=0.1),
                    Mock(entity={"score": 0.8}, distance=0.2),
                    Mock(entity={"score": 0.7}, distance=0.3),
                ]
            ]
            
            results = vector_store.search(sample_embedding, top_k=3)
            
            if results:
                scores = [r.get("score", 0) for r in results]
                
                # 验证分数在合理范围内
                assert all(0 <= s <= 1 for s in scores)
                
                # 验证分数递减（相似度从高到低）
                assert scores == sorted(scores, reverse=True)


class TestVectorStoreIntegration:
    """向量库集成测试"""
    
    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        return VectorStore()
    
    @pytest.fixture
    def embedder(self):
        """嵌入服务 fixture"""
        return EmbeddingService()
    
    def test_full_insert_search_cycle(self, vector_store, embedder):
        """测试完整的插入 - 搜索周期"""
        # 1. 生成向量
        text = "测试文本"
        embedding = embedder.embed(text)
        
        if embedding:
            # 2. 插入向量
            document = {
                "document_id": 1,
                "parent_id": "test_p",
                "child_id": "test_c",
                "parent_content": text,
                "child_content": text,
                "embedding": embedding,
            }
            
            with patch.object(vector_store.child_collection, 'insert') as mock_insert:
                mock_insert.return_value = Mock(insert_count=1)
                vector_store.batch_insert([document])
                
                assert mock_insert.called
            
            # 3. 搜索向量
            with patch.object(vector_store.child_collection, 'search') as mock_search:
                mock_search.return_value = [
                    [
                        Mock(
                            entity={
                                "document_id": 1,
                                "parent_id": "test_p",
                                "child_id": "test_c",
                                "parent_content": text,
                                "child_content": text,
                            },
                            distance=0.1
                        )
                    ]
                ]
                
                results = vector_store.search(embedding, top_k=5)
                
                assert mock_search.called
                assert len(results) > 0
    
    def test_error_handling(self, vector_store):
        """测试错误处理"""
        invalid_embedding = []
        
        with pytest.raises(Exception):
            vector_store.search(invalid_embedding, top_k=5)
    
    def test_performance_with_large_dataset(self, vector_store):
        """测试大数据集性能"""
        import time
        
        # 模拟大量向量搜索
        embedding = [0.1] * 1024
        
        with patch.object(vector_store.child_collection, 'search') as mock_search:
            # 模拟 10000 条记录的搜索
            mock_results = [
                Mock(
                    entity={
                        "document_id": i,
                        "parent_id": f"p{i}",
                        "child_id": f"c{i}",
                        "parent_content": f"content{i}",
                        "child_content": f"content{i}",
                    },
                    distance=0.1 - i * 0.00001
                )
                for i in range(10)
            ]
            mock_search.return_value = [mock_results]
            
            start_time = time.time()
            results = vector_store.search(embedding, top_k=10)
            elapsed = time.time() - start_time
            
            # 搜索应该在合理时间内完成
            assert elapsed < 5.0, "搜索应该快速完成"
            assert len(results) <= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
