
"""
检索质量评测引擎
================
对 Golden Dataset 中的每个问题执行实际检索，并与预期结果比较，计算各项指标。

运行模式:
    - REAL: 连接真实 Milvus + EmbeddingService，执行真实检索
    - MOCK: 使用模拟 EmbeddingService 和 Milvus，验证评测框架本身的逻辑

用法:
    from evaluation.retrieval_evaluator import RetrievalEvaluator
    evaluator = RetrievalEvaluator()
    results = evaluator.evaluate(golden_dataset)
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from .golden_dataset import GoldenQA, GOLDEN_DATASET

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """单个 QA 对的评测结果"""
    question: str
    difficulty: str
    category: str
    source_section: str
    
    # 检索结果
    retrieved_count: int = 0
    relevant_count: int = 0
    
    # 指标
    recall: float = 0.0        # Recall@k
    precision: float = 0.0     # Precision@k
    is_hit: bool = False       # top-1 是否命中
    mrr: float = 0.0           # MRR@k: first relevant rank reciprocal
    
    # 详情
    matched_keywords: List[str] = field(default_factory=list)
    missing_keywords: List[str] = field(default_factory=list)
    top_result_snippet: str = ""
    
    # 是否通过
    passed: bool = False


class RetrievalEvaluator:
    """
    检索质量评测器。
    
    对每个 Golden QA，执行检索并比对预期关键词/内容。
    """
    
    def __init__(self, top_k: int = 5, use_mock: bool = True):
        """
        Args:
            top_k: 检索返回的 top-k 条数
            use_mock: True 则使用模拟 EmbeddingService/Milvus 验证框架逻辑；
                      False 则对接真实检索服务（需要 Milvus + Embedding API 正常运行）
        """
        self.top_k = top_k
        self.use_mock = use_mock
        self._retrieval_service = None
    
    def _get_real_retrieval_service(self):
        """延迟初始化真实检索服务"""
        if self._retrieval_service is None:
            try:
                from app.services.retrieval_service import RetrievalService
                self._retrieval_service = RetrievalService()
                logger.info("已连接真实检索服务")
            except Exception as e:
                logger.warning(f"无法连接检索服务: {e}")
                raise
        return self._retrieval_service
    
    def _mock_search(self, question: str, expected_keywords: List[str]) -> List[Dict]:
        """
        模拟检索：确定性生成部分命中结果，模拟真实 RAG 行为。
        
        - 约 20% 的问题完全召不回相关内容（q_len % 5 == 0）
        - 其余按问题长度分配命中率：短问题 ~80%，长问题 ~40%
        
        确定性保证结果可复现。
        """
        import hashlib
        
        if not expected_keywords:
            return []
        
        seed = int(hashlib.md5(question.encode()).hexdigest()[:8], 16)
        q_len = len(question)
        
        # 确定性 miss：基于问题长度模 5，确保约 20% 的问题完全召不回
        if q_len % 5 == 0:
            return [{
                "score": 0.40,
                "child_content": "模拟检索: 未命中相关内容。本章节讨论的是其他管理条款。",
                "parent_content": "上海交通大学学生手册其他章节...",
            }]
        
        # 根据问题长度分配命中率
        if q_len < 15:
            hit_ratio = 0.80
            num_chunks = 2
        elif q_len < 25:
            hit_ratio = 0.60
            num_chunks = 3
        else:
            hit_ratio = 0.40
            num_chunks = 4
        
        n_hit = max(1, int(len(expected_keywords) * hit_ratio))
        hit_kws = expected_keywords[:n_hit]
        
        results = []
        per_chunk = max(1, len(hit_kws) // num_chunks)
        for i in range(min(num_chunks, 5)):
            start = i * per_chunk
            end = min(start + per_chunk, len(hit_kws))
            chunk_kws = hit_kws[start:end]
            if not chunk_kws:
                break
            score = round(0.95 - i * 0.12, 2)
            results.append({
                "score": score,
                "child_content": f"Mock#{i+1}: " + "，".join(chunk_kws),
                "parent_content": f"MockParent#{i+1}: 上海交通大学学生管理规定...",
            })
        
        return results
    
    def _local_api_search(self, question: str) -> List[Dict]:
        """
        通过本地后端 API 进行检索（绕过 Python 网络限制）。
        后端（uvicorn）通常可以正常连接 DashScope。
        """
        import urllib.request
        import json
        
        try:
            # 1. Login
            login_data = json.dumps({"username": "admin", "password": "123456"}).encode()
            login_req = urllib.request.Request(
                "http://localhost:8000/api/v1/auth/login",
                data=login_data,
                headers={"Content-Type": "application/json"},
            )
            login_resp = urllib.request.urlopen(login_req, timeout=10)
            token = json.loads(login_resp.read().decode()).get("access_token", "")
            
            # 2. Retrieve
            retrieve_data = json.dumps({"content": question, "top_k": 5}).encode()
            retrieve_req = urllib.request.Request(
                "http://localhost:8000/api/v1/chat/eval-retrieve",
                data=retrieve_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            retrieve_resp = urllib.request.urlopen(retrieve_req, timeout=60)
            results = json.loads(retrieve_resp.read().decode()).get("results", [])
            logger.info(f"本地 API 检索成功: question={question[:30]}..., results={len(results)}")
            return results
            
        except Exception as e:
            logger.warning(f"本地 API 检索失败，回退到直接调用: {e}")
            return self._direct_search(question)
    
    def _direct_search(self, question: str) -> List[Dict]:
        """直接调用 RetrievalService（需要本进程能连接 DashScope）"""
        service = self._get_real_retrieval_service()
        db = self._get_db()
        try:
            results = service.retrieve(question, top_k=self.top_k, db=db)
            return results
        except Exception as e:
            logger.error(f"直接检索失败: {e}")
            return []
        finally:
            if db:
                db.close()
    
    def _get_db(self):
        """获取数据库会话"""
        from app.core.database import SessionLocal
        return SessionLocal()

    def _real_search(self, question: str) -> List[Dict]:
        """真实检索：优先通过本地后端 API，失败时回退到直接调用"""
        return self._local_api_search(question)
    
    def _search(self, question: str, expected_keywords: List[str]) -> List[Dict]:
        """根据模式选择检索方式"""
        if self.use_mock:
            return self._mock_search(question, expected_keywords)
        else:
            return self._real_search(question)
    
    def _check_relevance(self, chunk: Dict, qa: GoldenQA) -> tuple:
        """
        检查单个 chunk 是否与 QA 相关。
        仅做严格子串匹配（大小写不敏感），不做模糊/部分匹配。
        返回 (is_relevant, matched_keywords)。
        """
        content = ""
        if isinstance(chunk, dict):
            for field in ("content", "child_content", "parent_content", "text"):
                val = chunk.get(field, "")
                if val:
                    content += val + " "
        
        content_lower = content.lower()
        
        matched = []
        
        # 1. 严格子串匹配 expected_keywords
        for kw in qa.expected_keywords:
            if kw.lower() in content_lower:
                matched.append(kw)
        
        # 2. 严格子串匹配 expected_content
        for ec in qa.expected_content:
            ec_lower = ec.lower()
            if ec_lower in content_lower:
                if ec not in matched:
                    matched.append(ec[:40])
        
        is_relevant = len(matched) > 0
        return is_relevant, matched
    
    def evaluate_single(self, qa: GoldenQA) -> EvaluationResult:
        """评测单个 QA 对"""
        results = self._search(qa.question, qa.expected_keywords)
        retrieved_count = len(results)
        
        relevant_count = 0
        all_matched_keywords = set()
        top_snippet = ""
        
        first_relevant_rank = None
        for rank, chunk in enumerate(results[:self.top_k]):
            is_rel, matched = self._check_relevance(chunk, qa)
            if is_rel:
                if first_relevant_rank is None:
                    first_relevant_rank = rank + 1
                relevant_count += 1
                all_matched_keywords.update(matched)
            
            if not top_snippet and isinstance(chunk, dict):
                top_snippet = (chunk.get("child_content", "") or "")[:120]
        
        mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
        
        total_expected = len(qa.expected_keywords) + len(qa.expected_content)
        # 召回率：匹配到的预期条目数 / 预期总数（上限 1.0）
        raw_recall = len(all_matched_keywords) / max(total_expected, 1) if total_expected > 0 else 0.0
        keyword_recall = min(raw_recall, 1.0)
        # Top-K 精准率：含关键词的chunk数 / 返回的chunk总数
        topk_precision = relevant_count / max(retrieved_count, 1) if retrieved_count > 0 else 0.0
        
        missing = []
        for kw in qa.expected_keywords:
            if kw not in all_matched_keywords:
                missing.append(kw)
        for ec in qa.expected_content:
            if ec[:40] not in all_matched_keywords:
                missing.append(ec[:40])
        
        is_hit = relevant_count > 0
        
        # Pass判定: 至少命中 2 个预期条目 或 命中率 >= 50%
        total_expected_items = len(qa.expected_keywords) + len(qa.expected_content)
        if total_expected_items <= 2:
            passed = is_hit  # 预期条目少时，命中1个即通过
        else:
            min_required = max(2, int(total_expected_items * 0.5))
            passed = len(all_matched_keywords) >= min_required
        
        return EvaluationResult(
            question=qa.question,
            difficulty=qa.difficulty,
            category=qa.category,
            source_section=qa.source_section,
            retrieved_count=retrieved_count,
            relevant_count=relevant_count,
            recall=keyword_recall,
            precision=topk_precision,
            is_hit=is_hit,
            mrr=mrr,
            matched_keywords=sorted(all_matched_keywords),
            missing_keywords=missing,
            top_result_snippet=top_snippet,
            passed=passed,
        )
    
    def evaluate(self, dataset: List[GoldenQA] = None) -> List[EvaluationResult]:
        """评测整个数据集"""
        if dataset is None:
            dataset = GOLDEN_DATASET
        
        results = []
        for qa in dataset:
            result = self.evaluate_single(qa)
            results.append(result)
        
        return results
    
    def print_report(self, results: List[EvaluationResult]):
        """打印可读的评测报告"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        hit = sum(1 for r in results if r.is_hit)
        
        print(f"\n{'='*60}")
        print(f"  检索质量评测报告")
        print(f"{'='*60}")
        print(f"  模式: {'MOCK' if self.use_mock else 'REAL'}")
        print(f"  总计: {total} 题")
        print(f"  通过: {passed}/{total} ({passed/total*100:.1f}%)")
        print(f"  至少命中1条: {hit}/{total} ({hit/total*100:.1f}%)")
        print()
        
        # 按难度统计详细指标
        for diff in ["easy", "medium", "hard"]:
            diff_results = [r for r in results if r.difficulty == diff]
            if diff_results:
                d_total = len(diff_results)
                d_passed = sum(1 for r in diff_results if r.passed)
                d_hit = sum(1 for r in diff_results if r.is_hit)
                d_recall = sum(r.recall for r in diff_results) / d_total
                d_precision = sum(r.precision for r in diff_results) / d_total
                d_mrr = sum(r.mrr for r in diff_results) / d_total
                print(f"  [{diff.upper()}] {d_total}题 | 通过:{d_passed}/{d_total}({d_passed/d_total*100:.0f}%)"
                      f" | 命中:{d_hit}/{d_total}({d_hit/d_total*100:.0f}%)"
                      f" | recall={d_recall:.3f} precision={d_precision:.3f} MRR={d_mrr:.3f}")
        
        print()
        
        # 失败的用例
        failed = [r for r in results if not r.passed]
        if failed:
            print(f"  {'-'*56}")
            print(f"  未通过的用例 ({len(failed)}):")
            print(f"  {'-'*56}")
            for r in failed:
                print(f"    Q: {r.question[:60]}")
                if r.missing_keywords:
                    print(f"    缺少: {r.missing_keywords[:3]}")
                print()
        
        # 汇总指标
        avg_recall = sum(r.recall for r in results) / total if total > 0 else 0
        avg_precision = sum(r.precision for r in results) / total if total > 0 else 0
        print(f"  {'-'*56}")
        print(f"  关键词召回率:    {avg_recall:.3f}")
        avg_mrr = sum(r.mrr for r in results) / total if total > 0 else 0
        print(f"  MRR@k:         {avg_mrr:.3f}")
        print(f"  Top-K 精准率: {avg_precision:.3f}")
        print(f"{'='*60}")
