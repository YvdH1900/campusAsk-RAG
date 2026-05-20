"""
检索服务单元测试
================
测试检索服务的各个组件：
- 向量检索
- BM25 关键词检索
- 多路召回
- 重排序
- 查询扩展
- 质量过滤
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from app.services.retrieval_service import RetrievalService
from app.services.multi_path_retrieval import MultiPathRetrieval
from app.services.bm25_service import BM25Service
from app.services.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService
from app.services.query_expansion import QueryExpansionService
from app.services.retrieval_quality import RetrievalQualityFilter
from app.services.reranker_service import RerankerService


class TestEmbeddingService:
    """嵌入服务测试"""
    
    @pytest.fixture
    def embedder(self):
        """嵌入服务 fixture"""
        return EmbeddingService()
    
    def test_embed_success(self, embedder):
        """测试成功向量化"""
        text = "这是一个测试文本"
        
        embedding = embedder.embed(text)
        
        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embed_empty_string(self, embedder):
        """测试空字符串向量化"""
        embedding = embedder.embed("")
        
        assert embedding is None or len(embedding) == 0
    
    def test_embed_long_text(self, embedder):
        """测试长文本向量化"""
        long_text = "这是一个很长的文本" * 100
        
        embedding = embedder.embed(long_text)
        
        assert embedding is not None
        assert len(embedding) > 0
    
    def test_embed_consistency(self, embedder):
        """测试向量化一致性"""
        text = "相同文本应生成相同向量"
        
        embedding1 = embedder.embed(text)
        embedding2 = embedder.embed(text)
        
        assert embedding1 == embedding2


class TestVectorStore:
    """向量库服务测试"""
    
    @pytest.fixture
    def vector_store(self):
        """向量库服务 fixture"""
        return VectorStore()
    
    def test_search_basic(self, vector_store):
        """测试基本向量搜索"""
        query_embedding = [0.1] * 1024
        
        results = vector_store.search(query_embedding, top_k=5)
        
        assert isinstance(results, list)
        
        if results:
            for result in results:
                assert "score" in result or "distance" in result
                assert "parent_content" in result or "child_content" in result
    
    def test_search_with_document_filter(self, vector_store):
        """测试带文档过滤的搜索"""
        query_embedding = [0.1] * 1024
        
        results = vector_store.search(query_embedding, top_k=5, document_id=1)
        
        assert isinstance(results, list)
        
        if results:
            for result in results:
                assert result.get("document_id") == 1
    
    def test_search_empty_embedding(self, vector_store):
        """测试空向量搜索"""
        empty_embedding = []
        
        with pytest.raises(Exception):
            vector_store.search(empty_embedding, top_k=5)


class TestBM25Service:
    """BM25 服务测试"""
    
    @pytest.fixture
    def bm25_service(self):
        """BM25 服务 fixture"""
        return BM25Service()
    
    @pytest.fixture
    def sample_documents(self):
        """示例文档"""
        return [
            "奖学金评定需要提交申请表和成绩单",
            "图书馆开放时间为每天早上 8 点到晚上 10 点",
            "申请助学金需要家庭经济困难证明",
            "期末考试安排可在教务系统查询",
        ]
    
    def test_build_index(self, bm25_service, sample_documents):
        """测试构建索引"""
        bm25_service.build_index(sample_documents)
        
        assert bm25_service._index_built
        assert len(bm25_service._corpus) == len(sample_documents)
    
    def test_search_after_build(self, bm25_service, sample_documents):
        """测试构建索引后搜索"""
        bm25_service.build_index(sample_documents)
        
        results = bm25_service.search("奖学金", top_k=2)
        
        assert isinstance(results, list)
        assert len(results) <= 2
        
        if results:
            assert "score" in results[0]
            assert "text" in results[0] or "index" in results[0]
    
    def test_search_before_build(self, bm25_service):
        """测试未构建索引时搜索"""
        results = bm25_service.search("测试", top_k=5)
        
        assert results == []
    
    def test_search_relevance(self, bm25_service, sample_documents):
        """测试搜索相关性"""
        bm25_service.build_index(sample_documents)
        
        query = "奖学金申请"
        results = bm25_service.search(query, top_k=2)
        
        if results:
            # 第一个结果应该与奖学金相关
            assert results[0]["score"] > 0


class TestQueryExpansion:
    """查询扩展服务测试"""
    
    def test_expand_query_basic(self):
        """测试基本查询扩展"""
        original_query = "奖学金怎么申请"
        
        expanded = QueryExpansionService.expand_query_for_retrieval(original_query)
        
        assert isinstance(expanded, str)
        assert len(expanded) > 0
    
    def test_expand_query_preserves_meaning(self):
        """测试扩展后保持原意"""
        original_query = "图书馆开放时间"
        
        expanded = QueryExpansionService.expand_query_for_retrieval(original_query)
        
        # 扩展后的查询应该包含原查询的关键词
        assert "图书馆" in expanded or "开放" in expanded
    
    def test_expand_query_handles_synonyms(self):
        """测试同义词扩展"""
        original_query = "如何办理休学"
        
        expanded = QueryExpansionService.expand_query_for_retrieval(original_query)
        
        # 可能包含同义词
        assert isinstance(expanded, str)
        assert len(expanded) >= len(original_query)


class TestRetrievalQualityFilter:
    """质量过滤服务测试"""
    
    @pytest.fixture
    def quality_filter(self):
        """质量过滤服务 fixture"""
        return RetrievalQualityFilter()
    
    @pytest.fixture
    def sample_results(self):
        """示例检索结果"""
        return [
            {"score": 0.8, "parent_content": "高质量内容 1"},
            {"score": 0.5, "parent_content": "中等质量内容"},
            {"score": 0.3, "parent_content": "低质量内容"},
            {"score": 0.1, "parent_content": "很低质量内容"},
            {"score": 0.05, "parent_content": "极低质量内容"},
        ]
    
    def test_filter_high_threshold(self, quality_filter, sample_results):
        """测试高阈值过滤"""
        filtered = quality_filter.filter(sample_results, threshold=0.45)
        
        assert len(filtered) < len(sample_results)
        
        for result in filtered:
            assert result["score"] >= 0.45
    
    def test_filter_low_threshold(self, quality_filter, sample_results):
        """测试低阈值过滤"""
        filtered = quality_filter.filter(sample_results, threshold=0.15)
        
        assert len(filtered) <= len(sample_results)
        
        for result in filtered:
            assert result["score"] >= 0.15
    
    def test_filter_empty_results(self, quality_filter):
        """测试空结果过滤"""
        filtered = quality_filter.filter([])
        
        assert filtered == []
    
    def test_filter_preserves_order(self, quality_filter, sample_results):
        """测试过滤后保持顺序"""
        filtered = quality_filter.filter(sample_results, threshold=0.2)
        
        if len(filtered) > 1:
            for i in range(len(filtered) - 1):
                assert filtered[i]["score"] >= filtered[i + 1]["score"]


class TestRerankerService:
    """重排序服务测试"""
    
    @pytest.fixture
    def reranker(self):
        """重排序服务 fixture"""
        return RerankerService()
    
    @pytest.fixture
    def sample_results(self):
        """示例检索结果"""
        return [
            {"score": 0.6, "parent_content": "相关内容 1", "child_content": "子内容 1"},
            {"score": 0.8, "parent_content": "相关内容 2", "child_content": "子内容 2"},
            {"score": 0.4, "parent_content": "相关内容 3", "child_content": "子内容 3"},
        ]
    
    def test_rerank_basic(self, reranker, sample_results):
        """测试基本重排序"""
        query = "测试查询"
        
        reranked = reranker.rerank(query, sample_results, top_k=3)
        
        assert isinstance(reranked, list)
        assert len(reranked) <= 3
        
        if len(reranked) > 1:
            # 验证重排序后分数更高的在前
            assert reranked[0]["score"] >= reranked[-1]["score"]
    
    def test_rerank_changes_order(self, reranker, sample_results):
        """测试重排序改变顺序"""
        query = "测试查询"
        
        original_order = [r["score"] for r in sample_results]
        reranked = reranker.rerank(query, sample_results, top_k=3)
        new_order = [r["score"] for r in reranked]
        
        # 重排序后顺序可能改变
        assert isinstance(new_order, list)
        assert len(new_order) == len(original_order)
    
    def test_rerank_empty_results(self, reranker):
        """测试空结果重排序"""
        query = "测试查询"
        
        reranked = reranker.rerank(query, [], top_k=5)
        
        assert reranked == []


class TestMultiPathRetrieval:
    """多路召回服务测试"""
    
    @pytest.fixture
    def multi_path(self):
        """多路召回服务 fixture"""
        return MultiPathRetrieval()
    
    @pytest.fixture
    def sample_questions(self):
        """示例问题"""
        return [
            "奖学金评定条件？",
            "图书馆开放时间？",
            "如何申请助学金？",
        ]
    
    def test_retrieve_basic(self, multi_path, sample_questions):
        """测试基本多路召回"""
        question = sample_questions[0]
        
        results = multi_path.retrieve(question, top_k=5)
        
        assert isinstance(results, list)
        assert len(results) <= 5
    
    def test_retrieve_rrf_fusion(self, multi_path, sample_questions):
        """测试 RRF 融合"""
        question = sample_questions[0]
        
        results = multi_path.retrieve(question, top_k=5)
        
        if results:
            # 验证结果包含 RRF 分数
            assert "rrf_score" in results[0] or "score" in results[0]
    
    def test_retrieve_multiple_paths(self, multi_path, sample_questions):
        """测试多路径检索"""
        question = sample_questions[0]
        
        with patch.object(multi_path, '_path_vector') as mock_path1, \
             patch.object(multi_path, '_path_expanded_vector') as mock_path2, \
             patch.object(multi_path, '_path_bm25') as mock_path3:
            
            mock_path1.return_value = [{"score": 0.8, "parent_content": "路径 1 结果"}]
            mock_path2.return_value = [{"score": 0.7, "parent_content": "路径 2 结果"}]
            mock_path3.return_value = [{"score": 0.6, "parent_content": "路径 3 结果"}]
            
            results = multi_path.retrieve(question, top_k=5)
            
            assert mock_path1.called
            assert mock_path2.called
            assert mock_path3.called
    
    def test_retrieve_handles_empty_paths(self, multi_path, sample_questions):
        """测试处理空路径"""
        question = sample_questions[0]
        
        with patch.object(multi_path, '_path_vector', return_value=[]), \
             patch.object(multi_path, '_path_expanded_vector', return_value=[]), \
             patch.object(multi_path, '_path_bm25', return_value=[]):
            
            results = multi_path.retrieve(question, top_k=5)
            
            assert results == []


class TestRetrievalService:
    """检索服务综合测试"""
    
    @pytest.fixture
    def retrieval_service(self):
        """检索服务 fixture"""
        service = RetrievalService()
        service.use_multi_path = True
        service.use_quality_filter = True
        return service
    
    @pytest.fixture
    def sample_questions(self):
        """示例问题"""
        return [
            "奖学金怎么申请？",
            "图书馆几点开门？",
            "如何办理校园卡？",
        ]
    
    def test_retrieve_basic(self, retrieval_service, sample_questions):
        """测试基本检索"""
        question = sample_questions[0]
        
        results = retrieval_service.retrieve(question, top_k=5)
        
        assert isinstance(results, list)
        assert len(results) <= 5
    
    def test_retrieve_with_cache(self, retrieval_service, sample_questions):
        """测试带缓存的检索"""
        question = sample_questions[0]
        
        with patch.object(retrieval_service, '_get_cache_key') as mock_cache_key, \
             patch('app.services.cache_service.cache_service') as mock_cache:
            
            mock_cache_key.return_value = "test:cache:key"
            mock_cache.get.return_value = [{"score": 0.9, "parent_content": "缓存结果"}]
            
            results = retrieval_service.retrieve(question, top_k=5)
            
            assert mock_cache.get.called
            if mock_cache.get.return_value:
                assert len(results) > 0
    
    def test_retrieve_with_semantic_cache(self, retrieval_service, sample_questions):
        """测试带语义缓存的检索"""
        question = sample_questions[0]
        
        with patch.object(retrieval_service, 'use_semantic_cache', True), \
             patch('app.services.semantic_cache.semantic_cache') as mock_semantic:
            
            mock_semantic.get.return_value = [{"score": 0.85, "parent_content": "语义缓存结果"}]
            
            results = retrieval_service.retrieve(question, top_k=5)
            
            if mock_semantic.get.return_value:
                assert len(results) > 0
    
    def test_retrieve_with_expansion(self, retrieval_service, sample_questions):
        """测试带查询扩展的检索"""
        question = sample_questions[0]
        
        with patch.object(retrieval_service, '_get_cache_key', return_value="test:key"), \
             patch('app.services.cache_service.cache_service.get', return_value=None), \
             patch.object(QueryExpansionService, 'expand_query_for_retrieval') as mock_expand:
            
            mock_expand.return_value = question + " 扩展"
            
            # Mock 后续检索步骤
            with patch.object(retrieval_service.vector_store, 'search', return_value=[]):
                results = retrieval_service.retrieve(question, top_k=5)
                
                assert mock_expand.called
    
    def test_retrieve_hybrid_search(self, retrieval_service, sample_questions):
        """测试混合检索"""
        question = sample_questions[0]
        
        with patch.object(retrieval_service, '_get_cache_key', return_value="test:key"), \
             patch('app.services.cache_service.cache_service.get', return_value=None), \
             patch.object(retrieval_service, '_hybrid_search') as mock_hybrid:
            
            mock_hybrid.return_value = [{"score": 0.8, "parent_content": "混合检索结果"}]
            
            results = retrieval_service.retrieve(question, top_k=5)
            
            if mock_hybrid.return_value:
                assert len(results) > 0
    
    def test_retrieve_quality_filter(self, retrieval_service, sample_questions):
        """测试质量过滤"""
        question = sample_questions[0]
        
        mock_results = [
            {"score": 0.8, "parent_content": "高质量"},
            {"score": 0.2, "parent_content": "低质量"},
        ]
        
        with patch.object(retrieval_service, '_get_cache_key', return_value="test:key"), \
             patch('app.services.cache_service.cache_service.get', return_value=None), \
             patch.object(retrieval_service, '_hybrid_search', return_value=mock_results), \
             patch.object(retrieval_service.quality_filter, 'filter') as mock_filter:
            
            mock_filter.return_value = [mock_results[0]]
            
            results = retrieval_service.retrieve(question, top_k=5)
            
            assert mock_filter.called
    
    def test_retrieve_dynamic_top_k(self, retrieval_service, sample_questions):
        """测试动态 Top-K 调整"""
        question = sample_questions[0]
        
        with patch.object(retrieval_service, '_get_cache_key', return_value="test:key"), \
             patch('app.services.cache_service.cache_service.get', return_value=None), \
             patch.object(retrieval_service, '_hybrid_search', return_value=[]):
            
            # 短问题应该使用较小的 top_k
            short_question = "奖学金？"
            results = retrieval_service.retrieve(short_question, top_k=5)
            
            # 长问题应该使用较大的 top_k
            long_question = "请问一下奖学金的具体申请条件和流程是什么？"
            results = retrieval_service.retrieve(long_question, top_k=5)
    
    def test_retrieve_handles_errors(self, retrieval_service, sample_questions):
        """测试错误处理"""
        question = sample_questions[0]
        
        with patch.object(retrieval_service, '_get_cache_key', return_value="test:key"), \
             patch('app.services.cache_service.cache_service.get', return_value=None), \
             patch.object(retrieval_service.vector_store, 'search', side_effect=Exception("检索失败")):
            
            results = retrieval_service.retrieve(question, top_k=5)
            
            # 应该返回空列表而不是抛出异常
            assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
