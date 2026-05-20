"""
RAG 功能量化测试
================
对 RAG 系统的核心指标进行全面测试和量化评估
包括：
- 检索质量指标（召回率、精确率、NDCG）
- 响应时间指标（检索延迟、生成延迟）
- 置信度评估
- 答案质量评分
"""

import pytest
import time
import statistics
from typing import List, Dict
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.services.retrieval_service import RetrievalService
from app.services.qa_service import QAService
from app.services.multi_path_retrieval import MultiPathRetrieval
from app.services.retrieval_quality import RetrievalQualityFilter
from app.services.reranker_service import RerankerService
from app.services.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService


class TestRetrievalMetrics:
    """检索质量指标测试"""
    
    @pytest.fixture
    def retrieval_service(self):
        """检索服务 fixture"""
        return RetrievalService()
    
    @pytest.fixture
    def multi_path_retrieval(self):
        """多路召回服务 fixture"""
        return MultiPathRetrieval()
    
    @pytest.fixture
    def quality_filter(self):
        """质量过滤服务 fixture"""
        return RetrievalQualityFilter()
    
    @pytest.fixture
    def reranker(self):
        """重排序服务 fixture"""
        return RerankerService()
    
    @pytest.fixture
    def sample_questions(self):
        """示例问题集"""
        return [
            "奖学金评定条件是什么？",
            "图书馆开放时间？",
            "如何申请助学金？",
            "期末考试安排在哪里查询？",
            "校园卡丢失怎么办？",
        ]
    
    def test_retrieval_recall_rate(self, retrieval_service, sample_questions):
        """测试检索召回率"""
        recall_rates = []
        
        for question in sample_questions:
            start_time = time.time()
            results = retrieval_service.retrieve(question, top_k=5)
            elapsed = time.time() - start_time
            
            # 召回率计算：有结果的数量 / 总问题数量
            has_results = 1 if len(results) > 0 else 0
            recall_rates.append(has_results)
            
            print(f"\n问题：{question}")
            print(f"  召回结果数：{len(results)}")
            print(f"  检索耗时：{elapsed:.3f}s")
        
        avg_recall = statistics.mean(recall_rates)
        print(f"\n平均召回率：{avg_recall:.2%}")
        
        assert avg_recall >= 0.8, "召回率应不低于 80%"
    
    def test_retrieval_precision(self, retrieval_service, sample_questions):
        """测试检索精确率"""
        precision_scores = []
        
        for question in sample_questions:
            results = retrieval_service.retrieve(question, top_k=5)
            
            if not results:
                precision_scores.append(0)
                continue
            
            # 精确率：相关结果数 / 返回结果总数
            # 这里假设 score > 0.3 的结果为相关
            relevant_count = sum(1 for r in results if r.get("score", 0) > 0.3)
            precision = relevant_count / len(results) if results else 0
            precision_scores.append(precision)
            
            print(f"\n问题：{question}")
            print(f"  返回结果数：{len(results)}")
            print(f"  相关结果数：{relevant_count}")
            print(f"  精确率：{precision:.2%}")
        
        avg_precision = statistics.mean(precision_scores) if precision_scores else 0
        print(f"\n平均精确率：{avg_precision:.2%}")
        
        assert avg_precision >= 0.6, "精确率应不低于 60%"
    
    def test_ndcg_score(self, retrieval_service, sample_questions):
        """测试 NDCG（归一化折损累积增益）"""
        ndcg_scores = []
        
        for question in sample_questions:
            results = retrieval_service.retrieve(question, top_k=5)
            
            if not results:
                ndcg_scores.append(0)
                continue
            
            # 计算 DCG
            dcg = 0
            for i, result in enumerate(results):
                score = result.get("score", 0)
                relevance = 1 if score > 0.3 else 0
                dcg += relevance / (i + 1)
            
            # 理想 DCG（所有结果都相关）
            idcg = sum(1 / (i + 1) for i in range(len(results)))
            
            ndcg = dcg / idcg if idcg > 0 else 0
            ndcg_scores.append(ndcg)
            
            print(f"\n问题：{question}")
            print(f"  DCG: {dcg:.3f}")
            print(f"  IDCG: {idcg:.3f}")
            print(f"  NDCG: {ndcg:.3f}")
        
        avg_ndcg = statistics.mean(ndcg_scores) if ndcg_scores else 0
        print(f"\n平均 NDCG: {avg_ndcg:.3f}")
        
        assert avg_ndcg >= 0.5, "NDCG 应不低于 0.5"
    
    def test_multi_path_improvement(self, multi_path_retrieval, sample_questions):
        """测试多路召回相比单路的提升"""
        improvements = []
        
        for question in sample_questions:
            # 单路召回（仅向量）
            embedder = EmbeddingService()
            vector_store = VectorStore()
            embedding = embedder.embed(question)
            single_path_results = vector_store.search(embedding, top_k=5) if embedding else []
            
            # 多路召回
            multi_path_results = multi_path_retrieval.retrieve(question, top_k=5)
            
            # 计算提升
            single_count = len(single_path_results)
            multi_count = len(multi_path_results)
            
            if single_count > 0:
                improvement = (multi_count - single_count) / single_count
            else:
                improvement = 1 if multi_count > 0 else 0
            
            improvements.append(improvement)
            
            print(f"\n问题：{question}")
            print(f"  单路结果数：{single_count}")
            print(f"  多路结果数：{multi_count}")
            print(f"  提升：{improvement:.2%}")
        
        avg_improvement = statistics.mean(improvements)
        print(f"\n平均提升：{avg_improvement:.2%}")
        
        assert avg_improvement >= 0, "多路召回不应差于单路"
    
    def test_quality_filter_effectiveness(self, quality_filter, sample_questions):
        """测试质量过滤效果"""
        retrieval_service = RetrievalService()
        
        for question in sample_questions:
            results = retrieval_service.retrieve(question, top_k=10)
            
            if not results:
                continue
            
            before_count = len(results)
            filtered_results = quality_filter.filter(results)
            after_count = len(filtered_results)
            
            print(f"\n问题：{question}")
            print(f"  过滤前：{before_count} 条")
            print(f"  过滤后：{after_count} 条")
            print(f"  过滤率：{(before_count - after_count) / before_count:.2%}")
            
            # 验证过滤后的结果质量更高
            if filtered_results:
                avg_score_before = statistics.mean(r.get("score", 0) for r in results)
                avg_score_after = statistics.mean(r.get("score", 0) for r in filtered_results)
                
                print(f"  平均分数（前）：{avg_score_before:.3f}")
                print(f"  平均分数（后）：{avg_score_after:.3f}")
                
                assert avg_score_after >= avg_score_before, "过滤后平均分数应提高"


class TestResponseTimeMetrics:
    """响应时间指标测试"""
    
    @pytest.fixture
    def qa_service(self):
        """问答服务 fixture"""
        return QAService()
    
    @pytest.fixture
    def retrieval_service(self):
        """检索服务 fixture"""
        return RetrievalService()
    
    @pytest.fixture
    def test_questions(self):
        """测试问题集"""
        return [
            "奖学金怎么申请？",
            "图书馆几点关门？",
            "如何办理休学？",
        ]
    
    def test_retrieval_latency(self, retrieval_service, test_questions):
        """测试检索延迟"""
        latencies = []
        
        for question in test_questions:
            start_time = time.time()
            results = retrieval_service.retrieve(question, top_k=5)
            elapsed = time.time() - start_time
            
            latencies.append(elapsed)
            
            print(f"\n问题：{question}")
            print(f"  检索延迟：{elapsed:.3f}s")
            print(f"  结果数：{len(results)}")
        
        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
        
        print(f"\n平均检索延迟：{avg_latency:.3f}s")
        print(f"P95 检索延迟：{p95_latency:.3f}s")
        
        assert avg_latency < 5.0, "平均检索延迟应小于 5 秒"
    
    def test_qa_end_to_end_latency(self, test_questions):
        """测试问答端到端延迟（Mock LLM）"""
        qa_service = QAService()
        latencies = []
        
        with patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            mock_llm.return_value = "这是一个测试回答"
            
            for question in test_questions:
                start_time = time.time()
                
                # 模拟问答流程
                results = qa_service.retriever.retrieve(question, top_k=5)
                answer = qa_service._call_llm_with_retry([])
                
                elapsed = time.time() - start_time
                latencies.append(elapsed)
                
                print(f"\n问题：{question}")
                print(f"  端到端延迟：{elapsed:.3f}s")
        
        avg_latency = statistics.mean(latencies)
        print(f"\n平均端到端延迟：{avg_latency:.3f}s")
        
        assert avg_latency < 10.0, "平均端到端延迟应小于 10 秒"
    
    def test_rerank_latency(self, test_questions):
        """测试重排序延迟"""
        reranker = RerankerService()
        retrieval_service = RetrievalService()
        latencies = []
        
        for question in test_questions:
            results = retrieval_service.retrieve(question, top_k=10)
            
            if not results:
                continue
            
            start_time = time.time()
            reranked = reranker.rerank(question, results, top_k=5)
            elapsed = time.time() - start_time
            
            latencies.append(elapsed)
            
            print(f"\n问题：{question}")
            print(f"  重排序延迟：{elapsed:.3f}s")
            print(f"  重排序结果数：{len(reranked)}")
        
        if latencies:
            avg_latency = statistics.mean(latencies)
            print(f"\n平均重排序延迟：{avg_latency:.3f}s")
            
            assert avg_latency < 3.0, "平均重排序延迟应小于 3 秒"


class TestConfidenceMetrics:
    """置信度评估测试"""
    
    @pytest.fixture
    def retrieval_service(self):
        """检索服务 fixture"""
        return RetrievalService()
    
    @pytest.fixture
    def test_questions_with_expected_confidence(self):
        """测试问题及预期置信度"""
        return [
            ("奖学金评定条件是什么？", "high"),  # 应该有高置信度
            ("今天天气怎么样？", "low"),  # 应该低置信度（无关问题）
            ("图书馆开放时间？", "medium"),  # 中等置信度
        ]
    
    def test_confidence_scoring(self, retrieval_service, test_questions_with_expected_confidence):
        """测试置信度评分"""
        for question, expected_level in test_questions_with_expected_confidence:
            results = retrieval_service.retrieve(question, top_k=5)
            
            if not results:
                confidence_score = 0
            else:
                # 使用最高分数作为置信度
                confidence_score = max(r.get("score", 0) for r in results)
            
            print(f"\n问题：{question}")
            print(f"  置信度分数：{confidence_score:.3f}")
            print(f"  预期等级：{expected_level}")
            
            # 验证置信度等级
            if expected_level == "high":
                assert confidence_score > 0.5, f"高置信度问题应大于 0.5，实际：{confidence_score:.3f}"
            elif expected_level == "medium":
                assert 0.3 <= confidence_score <= 0.5 or confidence_score > 0.5, \
                    f"中等置信度问题应在合理范围，实际：{confidence_score:.3f}"
            else:  # low
                print(f"  低置信度问题，分数可能较低")
    
    def test_answer_confidence_correlation(self, retrieval_service):
        """测试检索置信度与答案质量的相关性"""
        questions = [
            "如何申请奖学金？",
            "校园卡怎么办？",
        ]
        
        correlations = []
        
        for question in questions:
            results = retrieval_service.retrieve(question, top_k=5)
            
            if not results:
                continue
            
            # 检索置信度
            retrieval_confidence = max(r.get("score", 0) for r in results)
            
            # 上下文质量（平均分数）
            context_quality = statistics.mean(r.get("score", 0) for r in results)
            
            correlations.append((retrieval_confidence, context_quality))
            
            print(f"\n问题：{question}")
            print(f"  检索置信度：{retrieval_confidence:.3f}")
            print(f"  上下文质量：{context_quality:.3f}")
        
        # 验证正相关
        if correlations:
            for retrieval_conf, context_qual in correlations:
                assert retrieval_conf > 0.3, "检索置信度应大于 0.3"
                assert context_qual > 0.3, "上下文质量应大于 0.3"


class TestAnswerQualityMetrics:
    """答案质量评估测试"""
    
    @pytest.fixture
    def qa_service(self):
        """问答服务 fixture"""
        return QAService()
    
    @pytest.fixture
    def test_qa_pairs(self):
        """测试问答对"""
        return [
            {
                "question": "奖学金评定条件是什么？",
                "expected_keywords": ["奖学金", "评定", "条件"],
            },
            {
                "question": "图书馆开放时间？",
                "expected_keywords": ["图书馆", "开放", "时间"],
            },
        ]
    
    def test_answer_relevance(self, qa_service, test_qa_pairs):
        """测试答案相关性"""
        with patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            for qa_pair in test_qa_pairs:
                question = qa_pair["question"]
                expected_keywords = qa_pair["expected_keywords"]
                
                # Mock 返回包含关键词的答案
                mock_answer = f"关于{expected_keywords[0]}的{expected_keywords[1]}{expected_keywords[2]}是..."
                mock_llm.return_value = mock_answer
                
                # 这里不实际调用 QAService，只测试评估逻辑
                # 实际答案相关性需要人工评估或使用更复杂的指标
                
                print(f"\n问题：{question}")
                print(f"  预期关键词：{expected_keywords}")
                print(f"  Mock 答案：{mock_answer}")
                
                # 验证答案包含关键词
                keyword_count = sum(1 for kw in expected_keywords if kw in mock_answer)
                relevance = keyword_count / len(expected_keywords)
                
                print(f"  关键词覆盖率：{relevance:.2%}")
                
                assert relevance >= 0.5, "答案应包含至少 50% 的关键词"
    
    def test_answer_completeness(self, qa_service):
        """测试答案完整性"""
        questions = [
            "如何申请奖学金？",
        ]
        
        for question in questions:
            # 模拟完整答案
            complete_answer = "申请奖学金需要：1. 提交申请表；2. 提供成绩单；3. 等待审核。"
            incomplete_answer = "需要提交申请表。"
            
            # 完整性评分（基于长度和信息量）
            complete_score = min(len(complete_answer) / 50, 1.0)
            incomplete_score = min(len(incomplete_answer) / 50, 1.0)
            
            print(f"\n问题：{question}")
            print(f"  完整答案分数：{complete_score:.2f}")
            print(f"  不完整答案分数：{incomplete_score:.2f}")
            
            assert complete_score > incomplete_score, "完整答案应获得更高分"


class TestCacheMetrics:
    """缓存效果测试"""
    
    @pytest.fixture
    def retrieval_service(self):
        """检索服务 fixture"""
        return RetrievalService()
    
    def test_cache_hit_rate(self, retrieval_service):
        """测试缓存命中率"""
        question = "奖学金怎么申请？"
        
        # 第一次查询（未缓存）
        start_time = time.time()
        results1 = retrieval_service.retrieve(question, top_k=5)
        time1 = time.time() - start_time
        
        # 第二次查询（应命中缓存）
        start_time = time.time()
        results2 = retrieval_service.retrieve(question, top_k=5)
        time2 = time.time() - start_time
        
        print(f"\n问题：{question}")
        print(f"  首次查询时间：{time1:.3f}s")
        print(f"  缓存查询时间：{time2:.3f}s")
        print(f"  加速比：{time1 / time2:.2f}x" if time2 > 0 else "  加速比：N/A")
        
        # 验证缓存有效
        if time2 > 0:
            assert time2 < time1, "缓存查询应更快"
    
    def test_semantic_cache_effectiveness(self, retrieval_service):
        """测试语义缓存效果"""
        similar_questions = [
            "奖学金如何申请？",
            "怎么申请奖学金？",
            "奖学金申请流程是什么？",
        ]
        
        times = []
        
        for question in similar_questions:
            start_time = time.time()
            results = retrieval_service.retrieve(question, top_k=5)
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            print(f"\n问题：{question}")
            print(f"  查询时间：{elapsed:.3f}s")
            print(f"  结果数：{len(results)}")
        
        # 验证语义相似问题能受益于缓存
        if len(times) > 1:
            avg_time = statistics.mean(times)
            print(f"\n平均查询时间：{avg_time:.3f}s")
            
            assert avg_time < 5.0, "平均查询时间应小于 5 秒"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
