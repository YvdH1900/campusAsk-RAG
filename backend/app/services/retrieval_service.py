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
from app.models import ParentChunk
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
        self.use_multi_path = True  # 是否启用多路召回
        self.use_quality_filter = True  # 是否启用质量过滤
        self.use_semantic_cache = True  # 是否启用语义缓存
        self.use_ai_expansion = False  # 是否启用 AI 查询扩展
        self.use_reranking = True  # 是否启用重排序
        self._reranker_model_name = None  # AI 重排序模型名称（从 DB 加载）
        self._reranker_api_key = None  # AI 重排序 API Key
        self._last_rerank_method = None  # 记录上次使用的重排序方法
        self._full_bm25_built = False  # 全量BM25索引是否已构建
        self._full_bm25_docs = []       # 全量文档列表（child_content）
        self._full_bm25_ids = []        # 全量文档对应的 parent_id 列表
        self._full_bm25_doc_ids = []    # 全量文档对应的 document_id 列表
        self._llm_model_name = None  # LLM 模型名称（用于查询扩展等）
        self._last_expansion_method = None  # 记录上次使用的查询扩展方法

    def _load_settings_from_db(self, db=None):
        """从数据库加载功能开关配置"""
        if db:
            try:
                from app.models import SystemSetting
                for key, attr in [
                    ("query_expansion_enabled", "use_ai_expansion"),
                    ("reranking_enabled", "use_reranking"),
                ]:
                    setting = db.query(SystemSetting).filter(
                        SystemSetting.setting_key == key
                    ).first()
                    if setting:
                        setattr(self, attr, setting.setting_value == "true")
                        logger.info(f"从数据库加载配置 {key}: {getattr(self, attr)}")
            except Exception as e:
                logger.warning(f"读取功能配置失败: {e}")

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

    def _expand_split_group(
        self,
        hybrid_results: List[Dict],
        top_k: int,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict]:
        """
        拆分组扩展：当检索结果命中拆分文档时，补充同源其他文档的上下文
        
        Args:
            hybrid_results: 混合检索结果
            top_k: 目标结果数量
            query_embedding: 查询向量（用于向量检索排序）
            
        Returns:
            扩展结果列表
        """
        # 收集已命中的拆分组和文档ID
        split_groups = set()
        hit_doc_ids = set()
        
        for r in hybrid_results:
            sg = r.get("split_group_id")
            if sg:
                split_groups.add(sg)
            did = r.get("document_id")
            if did:
                hit_doc_ids.add(did)
        
        if not split_groups:
            return []
        
        # 对每个拆分组，查询同源其他文档的内容
        expanded = []
        remaining_slots = max(0, min(top_k * 2, len(hybrid_results) + 10) - len(hybrid_results))
        
        if remaining_slots <= 0:
            return []
        
        for sg in split_groups:
            sg_results = self.vector_store.search_by_split_group(
                split_group_id=sg,
                query_embedding=query_embedding,
                top_k=remaining_slots,
                exclude_document_ids=list(hit_doc_ids),
            )
            expanded.extend(sg_results)
            remaining_slots -= len(sg_results)
            if remaining_slots <= 0:
                break
        
        if expanded:
            logger.info(f"拆分组扩展: 补充了 {len(expanded)} 条同源文档结果")
        
        return expanded

    def _merge_and_dedup(
        self,
        original_results: List[Dict],
        expanded_results: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """
        合并原始结果和扩展结果，按 parent_id 去重
        
        Args:
            original_results: 原始检索结果
            expanded_results: 扩展结果（已有向量检索评分）
            top_k: 返回结果数量上限
            
        Returns:
            合并去重后的结果
        """
        seen_parent_ids = set(r.get("parent_id") for r in original_results)
        merged = list(original_results)
        
        for item in expanded_results:
            pid = item.get("parent_id")
            if pid not in seen_parent_ids:
                seen_parent_ids.add(pid)
                merged.append(item)
        
        # 按评分重新排序后截断
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged[:top_k]

    def _hybrid_search(
        self,
        query: str,
        vector_results: List[Dict],
        top_k: int,
        intent: Optional[str] = None,
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

        # 1. 全量 BM25 检索（不限于向量结果）
        if not self._full_bm25_built:
            try:
                all_entities = self.vector_store.child_collection.query(
                    expr="document_id > 0",
                    output_fields=["document_id", "parent_id", "child_content"],
                    limit=10000,
                )
                self._full_bm25_docs = []
                self._full_bm25_ids = []
                self._full_bm25_doc_ids = []
                for e in all_entities:
                    cc = e.get("child_content", "")
                    pid = e.get("parent_id", "")
                    if cc:
                        self._full_bm25_docs.append(cc)
                        self._full_bm25_ids.append(pid)
                        self._full_bm25_doc_ids.append(e.get("document_id"))
                if self._full_bm25_docs:
                    self.bm25_service.build_index(self._full_bm25_docs)
                self._full_bm25_built = True
            except Exception as e:
                logger.warning(f"全量BM25索引构建失败: {e}")
        
        full_bm25_by_pid = {}
        if self._full_bm25_built:
            full_bm25_results = self.bm25_service.search(query, top_k=top_k * 3)
            max_bm25 = max((r["score"] for r in full_bm25_results), default=1)
            for r in full_bm25_results:
                doc_id = r["doc_id"]
                if doc_id < len(self._full_bm25_ids):
                    pid = self._full_bm25_ids[doc_id]
                    score = r["score"] / max_bm25 if max_bm25 > 0 else 0
                    full_bm25_by_pid[pid] = max(full_bm25_by_pid.get(pid, 0), score)

        # 1.5 对候选集 parent_content 做额外 BM25（子块中无关键词但父块中有的场景）
        parent_bm25_by_pid = {}
        contents_for_bm25 = []
        pid_list_for_bm25 = []
        for vr in vector_results:
            pc = vr.get("content") or vr.get("parent_content") or ""
            if pc.strip():
                contents_for_bm25.append(pc)
                pid_list_for_bm25.append(str(vr.get("parent_id", "")))
        if contents_for_bm25:
            from app.services.bm25_service import BM25Service
            tmp_bm25 = BM25Service()
            tmp_bm25.build_index(contents_for_bm25)
            parent_bm25_results = tmp_bm25.search(query, top_k=min(len(contents_for_bm25), top_k * 2))
            max_pbm25 = max((r["score"] for r in parent_bm25_results), default=1)
            for r in parent_bm25_results:
                doc_id = r["doc_id"]
                if doc_id < len(pid_list_for_bm25):
                    pid = pid_list_for_bm25[doc_id]
                    score = r["score"] / max_pbm25 if max_pbm25 > 0 else 0
                    parent_bm25_by_pid[pid] = max(parent_bm25_by_pid.get(pid, 0), score)
        
        # 2. 动态权重：长文本查询增加 BM25 权重
        intent_weights = {
            "fact":     {"vector": 0.7, "bm25": 0.3},
            "process":  {"vector": 0.4, "bm25": 0.6},
            "policy":   {"vector": 0.5, "bm25": 0.5},
            "chat":     {"vector": 0.8, "bm25": 0.2},
        }
        if intent in intent_weights:
            bm25_weight = intent_weights[intent]["bm25"]
        else:
            chinese_chars = sum(1 for c in query if "\u4e00" <= c <= "\u9fff")
            bm25_weight = 0.5 if chinese_chars > 10 else 0.4
        vector_weight = 1.0 - bm25_weight
        
        # 3. 按 parent_id 匹配 BM25 分数（child_content + parent_content 双路 BM25）
        hybrid_results = []
        for i, vec_result in enumerate(vector_results):
            vec_score = vec_result.get("score", 0)
            pid = str(vec_result.get("parent_id", ""))
            full_bm25 = full_bm25_by_pid.get(pid, 0)
            parent_bm25 = parent_bm25_by_pid.get(pid, 0)
            total_bm25 = max(full_bm25, parent_bm25)
            
             # 父块 BM25 强匹配直接大幅加分（解决关键词只在父块中的场景）
            parent_boost = 0.0
            if parent_bm25 > 0.3:
                parent_boost = parent_bm25 * 0.6
            
            combined_score = vector_weight * vec_score + bm25_weight * total_bm25 + parent_boost
            
            hybrid_results.append({
                **vec_result,
                "score": round(combined_score, 4),
                "vector_score": round(vec_score, 4),
                "bm25_score": round(total_bm25, 4),
            })

        # 3.5 BM25 关键词兜底：逐词检索 embedding 遗漏的高匹配 chunk（至多1个）
        import jieba
        seen_pids = set(str(r.get("parent_id", "")) for r in hybrid_results)
        key_terms = [w for w in jieba.cut(query) if len(w) >= 2]
        bm25_kw_by_pid = {}
        for kw in key_terms[:5]:
            kw_results = self.bm25_service.search(kw, top_k=2)
            kw_max = max((r["score"] for r in kw_results), default=1)
            if kw_max <= 0:
                continue
            for r in kw_results:
                doc_id = r["doc_id"]
                if doc_id < len(self._full_bm25_ids):
                    pid = str(self._full_bm25_ids[doc_id])
                    if not pid:
                        continue
                    ns = r["score"] / kw_max
                    prev = bm25_kw_by_pid.get(pid, 0)
                    bonus = 0.25 if prev > 0 else 0
                    bm25_kw_by_pid[pid] = min(prev + bonus + ns * 0.7, 1.5)
        for pid, kw_score in sorted(bm25_kw_by_pid.items(), key=lambda x: x[1], reverse=True):
            if kw_score < 0.6 or pid in seen_pids:
                continue
            cc, did = "", None
            for i, p in enumerate(self._full_bm25_ids):
                if str(p) == pid:
                    cc = self._full_bm25_docs[i]
                    did = self._full_bm25_doc_ids[i] if i < len(self._full_bm25_doc_ids) else None
                    break
            if not cc:
                continue
            hybrid_results.append({
                "parent_id": pid, "document_id": did,
                "child_content": cc, "content": "", "parent_content": "",
                "score": round(vector_weight * 0.05 + bm25_weight * kw_score * 0.5, 4),
                "vector_score": 0.0, "bm25_score": round(kw_score, 4),
                "split_group_id": "",
            })
            break  # 至多注入1个

        # 4. 重排序（可关闭）
        if self.use_reranking:
            reranked = self.reranker.rerank(
                query, hybrid_results, top_k=top_k,
                ai_model_name=self._reranker_model_name,
                api_key=getattr(self, '_reranker_api_key', None)
            )
            # 记录使用的重排序方法
            if reranked:
                self._last_rerank_method = reranked[0].get("rerank_method", "unknown")
        else:
            # 关闭重排序，直接按混合评分排序返回
            reranked = sorted(hybrid_results, key=lambda x: x["score"], reverse=True)[:top_k]
            self._last_rerank_method = "disabled"

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
        # 不让意图分类器减少 top_k（评测需要更多结果来提高召回）
        dynamic_top_k = max(dynamic_top_k, top_k)
        logger.info(f"动态 Top-K: {top_k} -> {dynamic_top_k} (意图: {intent})")

        # 3. 语义缓存检查
        if self.use_semantic_cache:
            cached_answer = semantic_cache.search_similar(question, db=db)
            if cached_answer:
                logger.info(f"语义缓存命中，跳过检索")
                return cached_answer.get("contexts", [])

        # 3.5 加载重排序模型、LLM 模型和功能开关配置
        self._load_reranker_model(db)
        self._load_llm_model(db)
        self._load_settings_from_db(db)

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

        # 4.5 获取查询向量（用于拆分组扩展检索）
        query_embedding = self.embedder.embed(retrieval_query, db=db)
        if not query_embedding:
            logger.warning("问题向量化失败")
            return []

        # 5. 多路召回或单路检索
        if self.use_multi_path and dynamic_top_k >= 5:
            logger.info("使用多路召回策略")
            vector_results = multi_path_retrieval.retrieve(
                question=retrieval_query,
                top_k=max(dynamic_top_k * 3, 20),
                db=db,
            )
        else:
            # 单路检索：扩大候选池，确保低排名但含关键词的 chunk 能进入后续 BM25/重排序
            candidate_k = max(dynamic_top_k * 4, 30)
            vector_results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=candidate_k,
            )

        if not vector_results:
            logger.info("未检索到相关文档")
            return []

        # 6. 拆分组扩展：在重排序前补充同源拆分子文档的候选 chunk，
        #    让 Reranker 看到完整候选集，公平评估跨部分内容的相关性
        expanded_results = self._expand_split_group(vector_results, dynamic_top_k, query_embedding=query_embedding)
        if expanded_results:
            vector_results = self._merge_and_dedup(vector_results, expanded_results,len(vector_results) + len(expanded_results))

        # 6.5 回填 parent_content：尽早从 MySQL ParentChunk 表获取完整父块内容，
        #     确保后续的重排序、质量过滤、最终结果构建都使用完整上下文
        self._backfill_parent_content(vector_results, db)

        # 7. 混合检索（向量 + BM25 + 重排序）—— 此时候选池已包含同源文档
        # fact 短查询给 reranker 更多候选，解决 chunk 窗口导致正确 chunk 排名靠后的问题
        hybrid_top_k = max(dynamic_top_k, 15) if intent == "fact" else max(dynamic_top_k, 10)
        hybrid_results = self._hybrid_search(
            query=retrieval_query,
            vector_results=vector_results,
            top_k=hybrid_top_k,
            intent=intent,
        )

        if not hybrid_results:
            return []

        # 7.5 回填 BM25 注入 chunk 的 parent_content
        self._backfill_parent_content(hybrid_results, db)

        # 8. 质量过滤
        if self.use_quality_filter:
            hybrid_results = quality_filter.filter(hybrid_results)

        # 9. 权限过滤
        if user_role:
            hybrid_results = permission_filter.filter_by_role(
                hybrid_results,
                user_role,
            )

        # 10. 构建结果（补充文档元信息）
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

            # 优先使用重排序后的分数，它比 RRF 归一化分数更能反映真实相关性
            final_score = item.get("rerank_score") or item.get("score", 0)
            results.append({
                "content": item.get("parent_content") or item.get("child_content", ""),
                "child_content": item.get("child_content", ""),
                "parent_content": item.get("parent_content", ""),
                "source": doc_cache.get(doc_id, "未知文档"),
                "score": final_score,
                "document_id": doc_id,
                "vector_score": item.get("vector_score", 0),
                "bm25_score": item.get("bm25_score", 0),
                "split_group_id": item.get("split_group_id") or "",
            })
        # 按 score 排序（注入的 BM25 强匹配得分可能更高）
        results.sort(key=lambda x: x["score"], reverse=True)
        # 截断到 top_k，防止 BM25 兜底注入撑大结果集
        results = results[:dynamic_top_k]

        # 11. 写入缓存
        if results:
            cache_key = self._get_cache_key(question)
            cache_service.set(cache_key, results, self.cache_ttl)
            logger.info(f"检索结果已缓存，共 {len(results)} 条")

        logger.info(f"检索完成，返回 {len(results)} 条结果")
        return results

    def _backfill_parent_content(self, results: List[Dict], db: Optional[Session]) -> None:
        """
        从 MySQL ParentChunk 表批量回填 parent_content
        
        新架构：父块内容仅存 MySQL ParentChunk 表，
        向量检索/BM25 不再返回 parent_content，由本方法统一回填。
        
        Args:
            results: 检索结果列表（原地修改）
            db: 数据库会话
        """
        if not db or not results:
            if not results:
                return
            logger.warning("parent_content 回填跳过: db=None（检索服务未传入数据库会话）")
            return

        # 收集需要回填的 (document_id, parent_id) 对
        pairs = []
        seen = set()
        for r in results:
            doc_id = r.get("document_id")
            pid = r.get("parent_id")
            if doc_id is not None and pid is not None and pid != "":
                key = (doc_id, str(pid))
                if key not in seen:
                    seen.add(key)
                    pairs.append((doc_id, str(pid)))

        if not pairs:
            logger.warning(
                f"parent_content 回填跳过: {len(results)} 条结果均无有效的 (document_id, parent_id)"
            )
            return

        # 批量查询 ParentChunk
        try:
            doc_ids = list(set(p[0] for p in pairs))
            parent_chunks = (
                db.query(ParentChunk)
                .filter(ParentChunk.document_id.in_(doc_ids))
                .all()
            )

            if not parent_chunks:
                logger.warning(
                    f"parent_content 回填失败: ParentChunk 表中未找到 document_id={doc_ids} 的记录。"
                    f"请确认文档已重新上传/处理（父块内容依赖 MySQL parent_chunks 表）"
                )
                return

            # 构建查找表: (document_id, parent_id) -> parent_content
            pc_map = {}
            pc_parent_ids = set()
            for pc in parent_chunks:
                key = (pc.document_id, str(pc.parent_id))
                pc_map[key] = pc.parent_content or ""
                pc_parent_ids.add(str(pc.parent_id))

            # 回填每个结果
            filled_count = 0
            result_parent_ids = set(str(r.get("parent_id", "")) for r in results)

            for r in results:
                doc_id_val = r.get("document_id")
                pid_val = r.get("parent_id")
                if doc_id_val is not None and pid_val is not None:
                    key = (doc_id_val, str(pid_val))
                    pc = pc_map.get(key)
                    if pc:
                        r["parent_content"] = pc
                        # 如果 content 字段也是空的（之前靠 child_content 凑的），也更新
                        if not r.get("content"):
                            r["content"] = pc
                        filled_count += 1

            if filled_count > 0:
                logger.info(f"parent_content 回填完成: {filled_count}/{len(results)} 条")
            else:
                # parent_id 不匹配 —— 诊断日志
                logger.warning(
                    f"parent_content 回填失败: 0/{len(results)} 条匹配。"
                    f"结果中的 parent_id: {sorted(result_parent_ids)[:10]}，"
                    f"ParentChunk 中的 parent_id: {sorted(pc_parent_ids)[:10]}，"
                    f"document_id: {doc_ids}。"
                    f"请检查向量库与 MySQL 的 parent_id 格式是否一致"
                )
        except Exception as e:
            logger.warning(f"parent_content 回填异常: {e}", exc_info=True)

    def clear_cache(self):
        """清除检索缓存"""
        cache_service.clear_pattern("search:*")
        logger.info("检索缓存已清除")
