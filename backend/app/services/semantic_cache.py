"""
语义缓存服务
============
基于向量相似度的智能缓存机制
支持：
- 将用户问题向量存入 Redis
- 新问题时计算向量相似度
- 相似度超过阈值时直接返回缓存答案
- 大幅降低 LLM 调用成本
"""

import logging
import json
import hashlib
from typing import List, Dict, Optional
from app.services.cache_service import cache_service
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SemanticCacheService:
    """语义缓存服务"""

    CACHE_PREFIX = "semantic_cache:"
    SIMILARITY_THRESHOLD = 0.95  # 相似度阈值
    MAX_CACHE_SIZE = 1000  # 最大缓存条目数

    def __init__(self):
        """初始化语义缓存服务"""
        self.embedder = EmbeddingService()

    def _get_cache_key(self, question: str) -> str:
        """
        生成缓存键
        
        Args:
            question: 用户问题
            
        Returns:
            缓存键
        """
        import hashlib
        question_hash = hashlib.md5(question.encode("utf-8")).hexdigest()
        return f"{self.CACHE_PREFIX}{question_hash}"

    def _get_vector_key(self) -> str:
        """获取向量索引键"""
        return f"{self.CACHE_PREFIX}vectors"

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度分数 [0, 1]
        """
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def search_similar(
        self,
        question: str,
        threshold: Optional[float] = None,
        db=None,
    ) -> Optional[Dict]:
        """
        搜索语义相似的问题
        
        Args:
            question: 用户问题
            threshold: 相似度阈值
            db: 数据库会话
            
        Returns:
            缓存的答案，如果没有找到则返回 None
        """
        threshold = threshold or self.SIMILARITY_THRESHOLD

        # 1. 将问题向量化
        question_embedding = self.embedder.embed(question, db=db)
        if not question_embedding:
            return None

        # 2. 获取所有缓存问题的向量索引
        vector_key = self._get_vector_key()
        cached_vectors = cache_service.get(vector_key)
        
        if not cached_vectors:
            return None

        # 3. 计算相似度，找到最相似的问题
        best_match = None
        best_score = 0.0

        for cached_question_hash, cached_data in cached_vectors.items():
            cached_embedding = cached_data.get("embedding")
            if not cached_embedding:
                continue

            similarity = self._cosine_similarity(question_embedding, cached_embedding)
            
            if similarity > best_score:
                best_score = similarity
                best_match = cached_data

        # 4. 检查是否超过阈值
        if best_score >= threshold and best_match:
            logger.info(
                f"语义缓存命中: '{question[:30]}...' "
                f"(相似度: {best_score:.4f})"
            )
            return {
                "answer": best_match.get("answer"),
                "sources": best_match.get("sources", []),
                "context_count": best_match.get("context_count", 0),
                "confidence": best_match.get("confidence", "高"),
                "similarity": round(best_score, 4),
            }

        logger.info(f"语义缓存未命中: '{question[:30]}...' (最高相似度: {best_score:.4f})")
        return None

    def store(
        self,
        question: str,
        answer_data: Dict,
        embedding: Optional[List[float]] = None,
        db=None,
    ):
        """
        存储问题和答案到语义缓存
        
        Args:
            question: 用户问题
            answer_data: 答案数据
            embedding: 问题向量（如果已有）
            db: 数据库会话
        """
        # 1. 获取问题向量
        if not embedding:
            embedding = self.embedder.embed(question, db=db)
        
        if not embedding:
            logger.warning("无法存储语义缓存：问题向量化失败")
            return

        # 2. 存储到向量索引
        vector_key = self._get_vector_key()
        cached_vectors = cache_service.get(vector_key) or {}

        # 检查缓存大小
        if len(cached_vectors) >= self.MAX_CACHE_SIZE:
            # 删除最早的条目（简单策略）
            oldest_key = next(iter(cached_vectors))
            del cached_vectors[oldest_key]
            logger.info(f"语义缓存已满，删除旧条目")

        question_hash = hashlib.md5(question.encode("utf-8")).hexdigest()
        cached_vectors[question_hash] = {
            "embedding": embedding,
            "answer": answer_data.get("answer"),
            "sources": answer_data.get("sources", []),
            "context_count": answer_data.get("context_count", 0),
            "confidence": answer_data.get("confidence", "高"),
        }

        cache_service.set(vector_key, cached_vectors, ttl=86400 * 7)  # 7 天过期

        # 3. 同时存储到精确缓存（向后兼容）
        exact_key = self._get_cache_key(question)
        cache_service.set(exact_key, answer_data, ttl=86400 * 7)

        logger.info(f"语义缓存已存储: '{question[:30]}...'")


# 全局实例
semantic_cache = SemanticCacheService()
