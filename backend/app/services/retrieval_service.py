"""
检索服务（混合检索 + 查询扩展 + 重排序 + 多路召回 + 智能优化）
======================================================
基于用户问题从向量库检索相关文档
支持：
- 向量检索（语义匹配）
- BM25 关键词检索
- 查询扩展（同义词）
- 重排序（综合评分）
- 结果去重（按父块）
- 缓存热门查询结果
- 语义缓存（相似问题）
- 意图识别（动态策略）
- 动态 Top-K 调整
- 检索质量过滤
- 多路召回（RRF 融合）
- 基于角色的权限过滤
"""

import logging
from typing import List, Dict, Optional
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.bm25_service import BM25Service
from app.services.reranker_service import RerankerService
from app.services.query_expansion import QueryExpansionService
from app.services.cache_service import cache_service
from app.services.semantic_cache import semantic_cache
from app.services.intent_classifier import intent_classifier
from app.services.retrieval_quality import quality_filter
from app.services.multi_path_retrieval import multi_path_retrieval
from app.services.permission_filter import permission_filter
from app.models import Document
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RetrievalService:
    """混合检索服务（企业级增强版）"""

    def __init__(self):
        """初始化检索服务"""
        self.embedder = EmbeddingService()
        self.vector_store = VectorStore()
        self.bm25_service = BM25Service()
        self.reranker = RerankerService()
        self.cache_ttl = 3600  # 检索结果缓存 1 小时
        self._bm25_built = False
        self.use_multi_path = True  # 是否启用多路召回
        self.use_quality_filter = True  # 是否启用质量过滤
        self.use_semantic_cache = True  # 是否启用语义缓存
        self.use_ai_expansion = True  # 是否启用 AI 查询扩展
        self._reranker_model_name = None  # AI 重排序模型名称（从 DB 加载）
        self._reranker_api_key = None  # AI 重排序 API Key
        self._last_rerank_method = None  # 记录上次使用的重排序方法
        self._llm_model_name = None  # LLM 模型名称（用于查询扩展等）
        self._last_expansion_method = None  # 记录上次使用的查询扩展方法

    def _load_reranker_model(self, db=None):
        """从数据库加载重排序模型配置"""
        if self._reranker_model_name is not None:
            return
        if db:
            try:
                from app.models import ModelConfig
                active_reranker = db.query(ModelConfig).filter(
                    ModelConfig.model_type == "reranker",
                    ModelConfig.is_active == True
                ).first()
                if active_reranker:
                    self._reranker_model_name = active_reranker.model_name
                    self._reranker_api_key = active_reranker.api_key
                    logger.info(f"加载重排序模型: {self._reranker_model_name}")
            except Exception as e:
                logger.warning(f"读取重排序模型配置失败: {e}")

    def _load_llm_model(self, db=None):
        """从数据库加载 LLM 模型配置（用于查询扩展等辅助功能）"""
        if self._llm_model_name is not None:
            return
        if db:
            try:
                from app.models import ModelConfig
                active_llm = db.query(ModelConfig).filter(
                    ModelConfig.model_type == "llm",
                    ModelConfig.is_active == True
                ).first()
                if active_llm:
                    self._llm_model_name = active_llm.model_name
                    logger.info(f"从数据库加载 LLM 模型: {self._llm_model_name}")
            except Exception as e:
                logger.warning(f"读取 LLM 模型配置失败: {e}")

    def _get_cache_key(self, question: str) -> str:
        """
        生成检索缓存键
        
        Args:
            question: 用户问题
            
        Returns:
            缓存键
        """
        import hashlib
        question_hash = hashlib.md5(question.encode("utf-8")).hexdigest()
        return f"search:{question_hash}"

    def _build_bm25_index(self, contexts: List[Dict]):
        """
        构建 BM25 索引（惰性构建）
        
        Args:
            contexts: 文档内容列表
        """
        if not self._bm25_built and contexts:
            contents = [ctx.get("child_content", "") for ctx in contexts]
            self.bm25_service.build_index(contents)
            self._bm25_built = True

    def _hybrid_search(
        self,
        query: str,
        vector_results: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """
        混合检索：向量 + BM25 + 重排序
        
        Args:
            query: 用户问题
            vector_results: 向量检索结果
            top_k: 返回结果数量
            
        Returns:
            混合检索结果
        """
        if not vector_results:
            return []

        # 1. 构建 BM25 索引
        self._build_bm25_index(vector_results)

        # 2. BM25 关键词检索
        bm25_results = self.bm25_service.search(query, top_k=top_k * 2)

        # 3. 合并向量检索和 BM25 结果
        bm25_map = {r["doc_id"]: r["score"] for r in bm25_results}
        
        hybrid_results = []
        for i, vec_result in enumerate(vector_results):
            vec_score = vec_result.get("score", 0)
            bm25_score = bm25_map.get(i, 0)
            
            # 归一化 BM25 分数到 [0, 1]
            max_bm25 = max(bm25_map.values()) if bm25_map else 1
            normalized_bm25 = bm25_score / max_bm25 if max_bm25 > 0 else 0
            
            # 混合评分：向量 60% + BM25 40%
            combined_score = 0.6 * vec_score + 0.4 * normalized_bm25
            
            hybrid_results.append({
                **vec_result,
                "score": round(combined_score, 4),
                "vector_score": round(vec_score, 4),
                "bm25_score": round(normalized_bm25, 4),
            })

        # 4. 重排序
        reranked = self.reranker.rerank(
            query, hybrid_results, top_k=top_k,
            ai_model_name=self._reranker_model_name,
            api_key=getattr(self, '_reranker_api_key', None)
        )
        
        # 记录使用的重排序方法
        if reranked:
            self._last_rerank_method = reranked[0].get("rerank_method", "unknown")

        return reranked

    def get_feature_status(self) -> Dict[str, str]:
        """
        获取当前使用的功能状态
        
        Returns:
            功能状态字典
        """
        return {
            "rerank_method": self._last_rerank_method or "unknown",
            "reranker_model": self._reranker_model_name or "未配置",
            "expansion_method": self._last_expansion_method or "unknown",
            "multi_path": str(self.use_multi_path),
            "semantic_cache": str(self.use_semantic_cache),
        }

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        db: Optional[Session] = None,
        use_expansion: bool = True,
        user_role: Optional[str] = None,
    ) -> List[Dict]:
        """
        智能混合检索相关文档
        
        Args:
            question: 用户问题
            top_k: 返回结果数量
            db: 数据库会话（用于查询文档元信息）
            use_expansion: 是否使用查询扩展
            user_role: 用户角色（用于权限过滤）
            
        Returns:
            检索结果列表
        """
        # 1. 意图识别（动态调整策略）
        intent_result = intent_classifier.classify(question)
        intent = intent_result["intent"]
        strategy = intent_result["strategy"]
        
        # 如果是闲聊，直接返回空（不检索）
        if strategy.get("direct_answer"):
            logger.info(f"识别为闲聊，跳过检索: '{question[:30]}...'")
            return []

        # 2. 动态调整 top_k
        dynamic_top_k = strategy.get("top_k", top_k)
        logger.info(f"动态 Top-K: {top_k} -> {dynamic_top_k} (意图: {intent})")

        # 3. 语义缓存检查
        if self.use_semantic_cache:
            cached_answer = semantic_cache.search_similar(question, db=db)
            if cached_answer:
                logger.info(f"语义缓存命中，跳过检索")
                return cached_answer.get("contexts", [])

        # 3.5 加载重排序模型和 LLM 模型
        self._load_reranker_model(db)
        self._load_llm_model(db)

        # 4. 查询扩展（优先 AI 扩展，失败降级规则扩展）
        retrieval_query = question
        if use_expansion and strategy.get("use_expansion", True):
            use_ai_exp = self.use_ai_expansion and self._llm_model_name is not None
            retrieval_query = QueryExpansionService.expand_query_for_retrieval(
                question,
                use_ai=use_ai_exp,
                model_name=self._llm_model_name if use_ai_exp else None,
            )
            if retrieval_query != question:
                self._last_expansion_method = "ai" if use_ai_exp else "rule"
            else:
                self._last_expansion_method = "none"
            logger.info(f"扩展查询: '{question}' -> '{retrieval_query}'")

        # 5. 多路召回或单路检索
        if self.use_multi_path and dynamic_top_k >= 5:
            logger.info("使用多路召回策略")
            vector_results = multi_path_retrieval.retrieve(
                question=retrieval_query,
                top_k=dynamic_top_k,
                db=db,
            )
        else:
            # 单路检索
            query_embedding = self.embedder.embed(question, db=db)
            if not query_embedding:
                logger.warning("问题向量化失败")
                return []

            candidate_k = dynamic_top_k * 2
            vector_results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=candidate_k,
            )

        if not vector_results:
            logger.info("未检索到相关文档")
            return []

        # 6. 混合检索（向量 + BM25 + 重排序）
        hybrid_results = self._hybrid_search(
            query=retrieval_query,
            vector_results=vector_results,
            top_k=dynamic_top_k,
        )

        if not hybrid_results:
            return []

        # 7. 质量过滤
        if self.use_quality_filter:
            hybrid_results = quality_filter.filter(hybrid_results)
            
            # 如果过滤后结果不足，尝试扩展检索
            if len(hybrid_results) < dynamic_top_k // 2:
                logger.info("过滤后结果不足，触发扩展检索")
                # 可以降低阈值重试，这里简单返回现有结果

        # 8. 权限过滤
        if user_role:
            hybrid_results = permission_filter.filter_by_role(
                hybrid_results,
                user_role,
            )

        # 9. 构建结果（补充文档元信息）
        results = []
        doc_cache = {}

        for item in hybrid_results:
            doc_id = item.get("document_id")
            
            # 查询文档信息（带缓存）
            if doc_id not in doc_cache and db:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                doc_cache[doc_id] = doc.filename if doc else f"文档_{doc_id}"
            elif doc_id not in doc_cache:
                doc_cache[doc_id] = f"文档_{doc_id}"

            results.append({
                "content": item.get("parent_content", ""),
                "source": doc_cache.get(doc_id, "未知文档"),
                "score": item.get("score", 0),
                "document_id": doc_id,
                "vector_score": item.get("vector_score", 0),
                "bm25_score": item.get("bm25_score", 0),
            })

        # 10. 写入缓存
        if results:
            cache_key = self._get_cache_key(question)
            cache_service.set(cache_key, results, self.cache_ttl)
            logger.info(f"检索结果已缓存，共 {len(results)} 条")

        logger.info(f"检索完成，返回 {len(results)} 条结果")
        return results

    def clear_cache(self):
        """清除检索缓存"""
        cache_service.clear_pattern("search:*")
        logger.info("检索缓存已清除")
