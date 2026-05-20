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
        # 1. 三路检索
        path1_results = self._path_vector(question, top_k * 2, db=db)
        path2_results = self._path_expanded_vector(question, top_k * 2, db=db)
        path3_results = self._path_bm25(question, top_k * 2)

        logger.info(
            f"多路召回: 路径1={len(path1_results)}, "
            f"路径2={len(path2_results)}, 路径3={len(path3_results)}"
        )

        # 2. 使用 RRF 融合
        fused_results = self._rrf_fusion(
            [path1_results, path2_results, path3_results],
            top_k=top_k,
        )

        logger.info(f"多路召回完成，返回 {len(fused_results)} 条结果")
        return fused_results

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
                output_fields=["document_id", "parent_id", "child_id", "parent_content", "child_content"],
                limit=10000,
            )
            
            if not all_entities:
                logger.warning("向量库中没有文档数据，BM25路径返回空")
                return []
            
            # 去重：按 parent_id 去重，使用 parent_content
            seen_parents = {}
            for entity in all_entities:
                parent_id = entity.get("parent_id")
                if parent_id not in seen_parents:
                    seen_parents[parent_id] = entity
            
            # 构建BM25索引（使用父块内容）
            parent_contents = []
            parent_docs = []
            for parent_id, entity in seen_parents.items():
                content = entity.get("parent_content", "")
                if content:
                    parent_contents.append(content)
                    parent_docs.append({
                        "document_id": entity.get("document_id"),
                        "parent_id": parent_id,
                        "child_id": entity.get("child_id"),
                        "parent_content": content,
                        "child_content": entity.get("child_content", ""),
                    })
            
            if not parent_contents:
                return []
            
            self.bm25_service.build_index(parent_contents)
            
            # BM25检索
            bm25_results = self.bm25_service.search(question, top_k=top_k)
            
            # 转换为标准格式
            results = []
            for bm25_result in bm25_results:
                doc_id = bm25_result.get("doc_id")
                if doc_id is not None and doc_id < len(parent_docs):
                    parent_doc = parent_docs[doc_id]
                    results.append({
                        "document_id": parent_doc["document_id"],
                        "parent_id": parent_doc["parent_id"],
                        "child_id": parent_doc["child_id"],
                        "parent_content": parent_doc["parent_content"],
                        "child_content": parent_doc["child_content"],
                        "score": bm25_result.get("score", 0),
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


# 全局实例
multi_path_retrieval = MultiPathRetrieval()
