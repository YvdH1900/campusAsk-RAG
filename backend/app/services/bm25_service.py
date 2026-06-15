"""
BM25 关键词检索服务
==================
基于 BM25 算法的关键词检索
与向量检索互补，提高召回率
"""

import re
import math
import logging
import jieba
from typing import List, Dict, Optional
from collections import Counter
from sqlalchemy.orm import Session
from app.models import Document

logger = logging.getLogger(__name__)


class BM25Service:
    """BM25 关键词检索服务"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        初始化 BM25 服务
        
        Args:
            k1: 词频饱和参数（默认 1.5）
            b: 文档长度归一化参数（默认 0.75）
        """
        self.k1 = k1
        self.b = b
        self.documents = []
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.df = Counter()
        self.N = 0

    def _tokenize(self, text: str) -> List[str]:
        """
        中文分词
        
        Args:
            text: 原始文本
            
        Returns:
            分词列表
        """
        # 移除标点符号
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        # 使用 jieba 分词
        tokens = list(jieba.cut(text.lower()))
        # 过滤停用词和单字符
        stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '什么', '怎么', '如何', '可以', '那个', '这个', '哪些', '哪个', '谁', '为什么', '怎样', '几', '多', '少', '非常', '但是', '而且', '或者', '如果', '虽然', '因为', '所以', '然而', '不过', '之', '其', '该', '各', '每', '某', '被', '把', '对', '从', '向', '在', '于', '与', '和', '同', '跟', '为', '因', '由', '以', '按', '照', '依', '凭', '将', '让', '使', '叫', '给', '对', '比', '跟', '同', '除', '除了', '关', '关于', '对于'}
        return [t for t in tokens if t.strip() and t not in stop_words and len(t) > 1]

    def build_index(self, documents: List[str]):
        """
        构建 BM25 索引
        
        Args:
            documents: 文档列表
        """
        self.documents = []
        self.doc_lengths = []
        self.df = Counter()
        
        for doc in documents:
            tokens = self._tokenize(doc)
            self.documents.append(tokens)
            self.doc_lengths.append(len(tokens))
            # 统计文档频率
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.df[token] += 1
        
        self.N = len(documents)
        self.avg_doc_length = sum(self.doc_lengths) / max(self.N, 1)
        logger.info(f"BM25 索引构建完成，共 {self.N} 个文档")

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        BM25 检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            检索结果列表，格式:
            [
                {"doc_id": 0, "score": 2.5, "content": "文档内容"},
                ...
            ]
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * self.N

        for token in query_tokens:
            df = self.df.get(token, 0)
            if df == 0:
                continue

            # IDF 计算
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)

            for i, doc_tokens in enumerate(self.documents):
                tf = doc_tokens.count(token)
                doc_len = self.doc_lengths[i]
                
                # BM25 公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                scores[i] += idf * numerator / denominator

        # 排序返回 top_k
        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append({"doc_id": i, "score": round(score, 4)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
