"""
检索质量过滤器
==============
对检索结果进行质量过滤和评估
支持：
- 相似度阈值过滤
- 内容长度过滤
- 重复内容检测
- 结果质量评分
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RetrievalQualityFilter:
    """检索质量过滤器"""

    HIGH_THRESHOLD = 0.30  # 高质量阈值（优先使用）
    LOW_THRESHOLD = 0.15   # 降级阈值（结果不足时使用）
    MIN_RESULTS_COUNT = 3  # 最少保留结果数量
    MIN_CONTENT_LENGTH = 20  # 最低内容长度（字符）
    SIMILARITY_THRESHOLD_FOR_DUPLICATE = 0.9  # 重复检测阈值

    def filter(
        self,
        results: List[Dict],
        min_similarity: Optional[float] = None,
        min_length: Optional[int] = None,
    ) -> List[Dict]:
        """
        过滤低质量检索结果（自适应阈值策略）
        
        策略：
        1. 先使用高阈值过滤
        2. 如果结果数量 >= MIN_RESULTS_COUNT，直接返回
        3. 否则使用低阈值重新过滤，保留相对最好的结果
        
        Args:
            results: 原始检索结果
            min_similarity: 最低相似度阈值（可选，覆盖默认策略）
            min_length: 最低内容长度
            
        Returns:
            过滤后的结果
        """
        min_length = min_length or self.MIN_CONTENT_LENGTH

        if not results:
            return []

        # 如果指定了固定阈值，使用原有逻辑
        if min_similarity is not None:
            return self._filter_with_fixed_threshold(results, min_similarity, min_length)

        # 自适应阈值策略
        # 第一遍：使用高阈值
        high_threshold_results = self._filter_with_fixed_threshold(
            results, self.HIGH_THRESHOLD, min_length
        )
        
        if len(high_threshold_results) >= self.MIN_RESULTS_COUNT:
            logger.info(f"高阈值过滤: {len(results)} -> {len(high_threshold_results)} 条结果")
            return high_threshold_results

        # 第二遍：结果不足，使用低阈值
        low_threshold_results = self._filter_with_fixed_threshold(
            results, self.LOW_THRESHOLD, min_length
        )
        
        # 如果低阈值过滤后仍有结果，返回（最多保留 MIN_RESULTS_COUNT 个）
        if low_threshold_results:
            final_results = low_threshold_results[:max(self.MIN_RESULTS_COUNT, len(low_threshold_results))]
            logger.info(
                f"降级阈值过滤: {len(results)} -> {len(final_results)} 条结果 "
                f"(最高分: {final_results[0].get('score', 0):.4f})"
            )
            return final_results

        # 极端情况：所有结果都被过滤，返回空
        logger.warning(f"所有结果被过滤，返回空结果")
        return []

    def _filter_with_fixed_threshold(
        self,
        results: List[Dict],
        threshold: float,
        min_length: int,
    ) -> List[Dict]:
        """使用固定阈值过滤"""
        filtered = []
        
        for result in results:
            # 1. 相似度过滤
            score = result.get("rerank_score") or result.get("score", 0)
            if score < threshold:
                continue
            
            # 2. 内容长度过滤（兼容 content 和 parent_content 字段）
            content = result.get("content") or result.get("parent_content", "")
            if len(content) < min_length:
                continue
            
            filtered.append(result)
        
        # 3. 去重
        filtered = self._remove_duplicates(filtered)
        
        return filtered

    def _remove_duplicates(self, results: List[Dict]) -> List[Dict]:
        """
        去除重复内容
        
        Args:
            results: 检索结果列表
            
        Returns:
            去重后的结果
        """
        if not results:
            return []

        unique_results = []
        seen_contents = []
        
        for result in results:
            # 兼容 content 和 parent_content 字段
            content = result.get("content") or result.get("parent_content", "")
            is_duplicate = False
            
            for seen_content in seen_contents:
                similarity = self._text_similarity(content, seen_content)
                if similarity > self.SIMILARITY_THRESHOLD_FOR_DUPLICATE:
                    is_duplicate = True
                    logger.debug(f"检测到重复内容，相似度: {similarity:.4f}")
                    break
            
            if not is_duplicate:
                unique_results.append(result)
                seen_contents.append(content)
        
        return unique_results

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        计算文本相似度（基于 Jaccard 相似度）
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度分数 [0, 1]
        """
        if not text1 or not text2:
            return 0.0

        # 分词（简单按字符 n-gram）
        set1 = set(text1[i:i+3] for i in range(len(text1) - 2))
        set2 = set(text2[i:i+3] for i in range(len(text2) - 2))
        
        if not set1 or not set2:
            return 0.0

        intersection = set1 & set2
        union = set1 | set2
        
        return len(intersection) / len(union)

    def evaluate_quality(self, results: List[Dict]) -> Dict:
        """
        评估检索结果质量
        
        Args:
            results: 检索结果列表
            
        Returns:
            质量评估报告
        """
        if not results:
            return {
                "quality_score": 0.0,
                "avg_similarity": 0.0,
                "avg_content_length": 0,
                "has_results": False,
            }

        similarities = [r.get("score", 0) for r in results]
        content_lengths = [len(r.get("content", "")) for r in results]
        
        avg_similarity = sum(similarities) / len(similarities)
        avg_content_length = sum(content_lengths) / len(content_lengths)
        
        # 质量评分：相似度 60% + 内容长度 40%
        length_score = min(avg_content_length / 500, 1.0)  # 500 字为满分
        quality_score = 0.6 * avg_similarity + 0.4 * length_score
        
        return {
            "quality_score": round(quality_score, 4),
            "avg_similarity": round(avg_similarity, 4),
            "avg_content_length": round(avg_content_length, 2),
            "result_count": len(results),
            "has_results": True,
        }


# 全局实例
quality_filter = RetrievalQualityFilter()
