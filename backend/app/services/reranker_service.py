"""
重排序服务
==========
对检索结果进行重排序，提升最终结果质量
支持两种模式：
1. API 重排序：使用阿里云百炼平台的 Reranker API（推荐，效果好，无需本地模型）
2. 启发式重排序：基于向量分数和关键词匹配的加权融合（fallback，零成本）
"""

import logging
import time
import os
from typing import List, Dict, Any, Optional
import jieba
import dashscope
from http import HTTPStatus

logger = logging.getLogger(__name__)


class RerankerService:
    """重排序服务"""

    def __init__(self):
        self._api_key = None
        self._model_name = None
        self._use_api = False

    def _init_api(self, model_name: str = "gte-rerank", api_key: Optional[str] = None):
        """初始化 API 重排序"""
        if self._model_name == model_name and self._use_api:
            return
        
        try:
            # 优先使用传入的 API Key，否则从环境变量读取
            key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
            
            if not key:
                logger.warning("Reranker API Key 未配置，使用启发式重排序")
                self._use_api = False
                return
            
            self._api_key = key
            self._model_name = model_name
            self._use_api = True
            logger.info(f"API 重排序已初始化: {model_name}")
            
        except Exception as e:
            logger.warning(f"API 重排序初始化失败: {e}，使用启发式重排序")
            self._use_api = False

    def rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 5, 
               ai_model_name: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        对检索结果进行重排序
        
        Args:
            query: 用户问题
            results: 检索结果列表
            top_k: 返回数量
            ai_model_name: 模型名称（如 "gte-rerank"）
            api_key: API Key（可选）
            
        Returns:
            重排序后的结果列表
        """
        if not results:
            return results
        
        # 尝试使用 API 重排序
        if ai_model_name:
            self._init_api(ai_model_name, api_key)
        
        if self._use_api:
            logger.info(f"使用 API 重排序: {self._model_name}")
            return self._api_rerank(query, results, top_k)
        else:
            logger.info(f"使用启发式重排序 (API Key 未配置或初始化失败)")
            return self._heuristic_rerank(query, results, top_k)

    def _api_rerank(self, query: str, results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """使用 API 进行重排序"""
        try:
            start_time = time.time()
            
            # 准备文档列表（兼容多种字段名）
            documents = []
            doc_to_result_index = []
            content_key = "content"
            for i, r in enumerate(results):
                content = r.get("content") or r.get("parent_content") or r.get("child_content") or r.get("text", "")
                if content:
                    documents.append(content)
                    doc_to_result_index.append(i)
                    if content_key == "content" and not r.get("content"):
                        content_key = "parent_content" if r.get("parent_content") else ("child_content" if r.get("child_content") else "text")
            
            if not documents:
                logger.warning(f"重排序跳过: 所有结果均无有效内容字段，返回原始结果 {len(results[:top_k])} 条")
                for r in results[:top_k]:
                    r["rerank_method"] = "heuristic"
                    r["rerank_score"] = r.get("score", 0.5)
                return results[:top_k]
            
            # 设置 API Key
            original_key = dashscope.api_key
            dashscope.api_key = self._api_key
            
            try:
                # 调用阿里云百炼平台的 Reranker API
                response = dashscope.TextReRank.call(
                    model=self._model_name,
                    query=query,
                    documents=documents,
                    top_n=len(documents)
                )
                
                if response.status_code == HTTPStatus.OK and response.output:
                    # 将分数附加到结果中
                    scored_results = []
                    rerank_results = response.output.get("results", [])
                    
                    # 创建结果映射
                    result_map = {i: r for i, r in enumerate(results)}
                    
                    for rerank_item in rerank_results:
                        doc_index = rerank_item.get("index", 0)
                        result_index = doc_to_result_index[doc_index] if doc_index < len(doc_to_result_index) else None
                        score = rerank_item.get("relevance_score", 0)
                        
                        if result_index is not None and result_index in result_map:
                            r = result_map[result_index]
                            r["rerank_score"] = float(score)
                            r["rerank_method"] = "api"
                            scored_results.append(r)
                    
                    # 按重排序分数排序
                    scored_results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
                    
                    elapsed = time.time() - start_time
                    logger.info(f"API 重排序完成: {len(results)} -> {min(top_k, len(scored_results))} 条结果，耗时 {elapsed:.3f}s")
                    
                    return scored_results[:top_k]
                else:
                    logger.warning(f"API 重排序失败: {response.message}，降级到启发式重排序")
                    return self._heuristic_rerank(query, results, top_k)
                    
            finally:
                # 恢复原始 API Key
                dashscope.api_key = original_key
            
        except Exception as e:
            logger.error(f"API 重排序失败: {e}，降级到启发式重排序")
            self._use_api = False
            return self._heuristic_rerank(query, results, top_k)

    def _heuristic_rerank(self, query: str, results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """基于分数的启发式重排序（fallback）"""
        query_lower = query.lower()
        query_words = set(jieba.cut(query_lower))
        
        scored_results = []
        for r in results:
            content = r.get("content") or r.get("parent_content") or r.get("child_content") or r.get("text", "")
            content_lower = content.lower()
            content_words = set(jieba.cut(content_lower))
            
            # 向量检索分数（已有）
            vector_score = r.get("score", r.get("vector_score", 0.5))
            
            # 关键词匹配度
            if content_words:
                keyword_overlap = len(query_words & content_words) / max(len(query_words), 1)
            else:
                keyword_overlap = 0
            
            # 综合评分 = 向量分数 70% + 关键词匹配 30%
            combined_score = 0.7 * vector_score + 0.3 * keyword_overlap
            
            r["rerank_score"] = combined_score
            r["rerank_method"] = "heuristic"
            scored_results.append(r)
        
        scored_results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        logger.info(f"启发式重排序完成: {len(results)} -> {min(top_k, len(scored_results))} 条结果")
        return scored_results[:top_k]

    def is_api_available(self) -> bool:
        """检查 API 重排序是否可用"""
        return self._use_api


# 全局单例
reranker_service = RerankerService()
