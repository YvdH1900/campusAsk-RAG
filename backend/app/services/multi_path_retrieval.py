"""
多路召回服务
============
使用多种检索路径提高召回率
支持：
- 路径1：原始问题向量检索
- 路径2：扩展问题向量检索
- 路径3：BM25 关键词检索
- 使用 RRF（Reciprocal Rank Fusion）算法融合结果
"""

import logging
from typing import List, Dict
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.bm25_service import BM25Service
from app.services.query_expansion import QueryExpansionService

logger = logging.getLogger(__name__)


class MultiPathRetrieval:
    """多路召回服务"""

    def __init__(self):
        """初始化多路召回服务"""
        self.embedder = EmbeddingService()
        self.vector_store = VectorStore()
        self.bm25_service = BM25Service()

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        db=None,
    ) -> List[Dict]:
        """
        多路召回
        
        Args:
            question: 用户问题
            top_k: 返回结果数量
            db: 数据库会话
            
        Returns:
            融合后的检索结果
        """
        # 扩大检索范围，确保跨子文档覆盖
        expanded_top_k = max(top_k, 15)

        # 1. 三路检索
        path1_results = self._path_vector(question, expanded_top_k, db=db)
        path2_results = self._path_expanded_vector(question, expanded_top_k, db=db)
        path3_results = self._path_bm25(question, expanded_top_k)

        logger.info(
            f"多路召回: 路径1={len(path1_results)}, "
            f"路径2={len(path2_results)}, 路径3={len(path3_results)}"
        )

        # 2. 使用 RRF 融合
        fused_results = self._rrf_fusion(
            [path1_results, path2_results, path3_results],
            top_k=expanded_top_k,
        )

        # 3. 跨文档多样性增强：确保每个拆分组至少返回 1-2 个 chunk
        diversified_results = self._ensure_doc_diversity(fused_results, min_per_doc=2)

        # 4. 按 score 重新排序，取 top_k
        final_results = sorted(diversified_results, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        logger.info(f"多路召回完成，返回 {len(final_results)} 条结果")
        return final_results

    def _path_vector(self, question: str, top_k: int, db=None) -> List[Dict]:
        """路径1：原始问题向量检索"""
        embedding = self.embedder.embed(question, db=db)
        if not embedding:
            return []

        results = self.vector_store.search(
            query_embedding=embedding,
            top_k=top_k,
        )

        return results

    def _path_expanded_vector(self, question: str, top_k: int, db=None) -> List[Dict]:
        """路径2：扩展问题向量检索"""
        expanded_query = QueryExpansionService.expand_query_for_retrieval(question)
        
        if expanded_query == question:
            return []

        embedding = self.embedder.embed(expanded_query, db=db)
        if not embedding:
            return []

        results = self.vector_store.search(
            query_embedding=embedding,
            top_k=top_k,
        )

        return results

    def _path_bm25(self, question: str, top_k: int) -> List[Dict]:
        """路径3：BM25 关键词检索（使用向量库中的子块内容）"""
        try:
            # 从向量库查询所有子块内容
            all_entities = self.vector_store.child_collection.query(
                expr="document_id > 0",
                output_fields=["document_id", "parent_id", "child_id", "parent_content", "child_content", "split_group_id"],
                limit=10000,
            )
            
            if not all_entities:
                logger.warning("向量库中没有文档数据，BM25路径返回空")
                return []
            
            # 使用全部子块内容构建BM25索引（761条×200字，粒度与向量搜索一致）
            child_contents = []
            child_docs = []
            for entity in all_entities:
                content = entity.get("child_content", "")
                if content:
                    child_contents.append(content)
                    child_docs.append({
                        "document_id": entity.get("document_id"),
                        "parent_id": entity.get("parent_id"),
                        "child_id": entity.get("child_id"),
                        "parent_content": entity.get("parent_content", ""),
                        "child_content": content,
                        "split_group_id": entity.get("split_group_id") or "",
                    })

            if not child_contents:
                return []

            self.bm25_service.build_index(child_contents)

            # BM25检索
            bm25_results = self.bm25_service.search(question, top_k=top_k)

            # 转换为标准格式
            results = []
            for bm25_result in bm25_results:
                doc_id = bm25_result.get("doc_id")
                if doc_id is not None and doc_id < len(child_docs):
                    doc = child_docs[doc_id]
                    results.append({
                        "child_content": doc["child_content"],
                        "parent_content": doc["parent_content"],
                        "score": bm25_result["score"],
                        "source": "BM25-" + str(doc["parent_id"]),
                        "rerank_method": "bm25",
                        "doc_id": doc_id,
                        "parent_id": doc["parent_id"],
                        "document_id": doc["document_id"],
                        "split_group_id": doc["split_group_id"],
                    })
            return results
        except Exception as e:
            logger.error(f"BM25检索失败: {str(e)}")
            return []

    def _rrf_fusion(
        self,
        result_lists: List[List[Dict]],
        top_k: int,
        k: int = 60,
    ) -> List[Dict]:
        """
        RRF（Reciprocal Rank Fusion）融合多路检索结果
        
        Args:
            result_lists: 多路检索结果列表
            top_k: 返回结果数量
            k: RRF 常数（通常 60）
            
        Returns:
            融合后的结果
        """
        # 计算每个文档的 RRF 分数
        rrf_scores = {}
        doc_map = {}

        for results in result_lists:
            for rank, result in enumerate(results, 1):
                # 使用 parent_id 作为唯一标识（同一个文档有多个不同的父块）
                unique_id = result.get("parent_id") or result.get("document_id") or result.get("child_id")
                if not unique_id:
                    continue

                # RRF 公式：1 / (k + rank)
                rrf_score = 1.0 / (k + rank)
                
                if unique_id not in rrf_scores:
                    rrf_scores[unique_id] = 0.0
                    doc_map[unique_id] = result
                
                rrf_scores[unique_id] += rrf_score

        # 按 RRF 分数排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # 构建最终结果
        fused_results = []
        for unique_id, score in sorted_docs[:top_k]:
            result = doc_map[unique_id].copy()
            result["rrf_score"] = round(score, 4)
            fused_results.append(result)

        # 归一化 RRF 分数到 [0, 1] 范围
        if fused_results:
            max_score = max(r["rrf_score"] for r in fused_results)
            if max_score > 0:
                for r in fused_results:
                    r["score"] = round(r["rrf_score"] / max_score, 4)
            else:
                for r in fused_results:
                    r["score"] = 1.0

        return fused_results

    def _ensure_doc_diversity(
        self,
        results: List[Dict],
        min_per_doc: int = 2,
    ) -> List[Dict]:
        """
        跨文档多样性增强：确保每个拆分组至少返回 min_per_doc 个 chunk
        
        当只有一个文档组时，不做限制，返回全部结果。
        当有多个文档组时，确保每组至少拿到 min_per_doc 个名额，
        其余名额按分数高低分配。
        
        Args:
            results: RRF 融合后的检索结果
            min_per_doc: 每个拆分组最少返回的 chunk 数量
            
        Returns:
            增强多样性后的结果列表
        """
        if not results:
            return []

        # 按 split_group_id 分组（空 split_group_id 的视为独立文档）
        doc_groups = {}
        for r in results:
            group_id = r.get("split_group_id") or f"doc_{r.get('document_id', 'unknown')}"
            doc_groups.setdefault(group_id, []).append(r)

        # 只有一个文档组时，不需要做多样性限制，返回全部结果
        if len(doc_groups) <= 1:
            return results

        # 多个文档组：确保每组至少拿到 min_per_doc 个名额
        num_groups = len(doc_groups)
        reserved = []
        used_ids = set()

        for group_id, chunks in doc_groups.items():
            quota = min(min_per_doc, len(chunks))
            for c in chunks[:quota]:
                pid = c.get("parent_id")
                if pid and pid not in used_ids:
                    used_ids.add(pid)
                    reserved.append(c)

        # 剩余名额按分数从高到低填充（跳过已使用的 parent_id）
        remaining = [
            r for r in results
            if r.get("parent_id") not in used_ids
        ]
        remaining.sort(key=lambda x: x.get("score", 0), reverse=True)

        return reserved + remaining


# 全局实例
multi_path_retrieval = MultiPathRetrieval()
