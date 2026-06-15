
"""
检索质量评测测试
================
对 Golden Dataset 运行检索质量评估，验证 RAG 系统的检索能力。

标记说明:
    @pytest.mark.evaluation   - 所有评测测试
    @pytest.mark.retrieval    - 检索质量评测
    @pytest.mark.mock         - 使用 mock 模式（离线）
    @pytest.mark.real         - 使用真实检索服务（需要外部依赖）
"""

import pytest
from .golden_dataset import GOLDEN_DATASET, get_dataset_stats, get_questions_by_difficulty


# ============================================================
# 基础测试: 数据集本身是完整的
# ============================================================

class TestGoldenDatasetIntegrity:
    """验证 Golden Dataset 本身的完整性"""

    def test_dataset_not_empty(self):
        """数据集不能为空"""
        assert len(GOLDEN_DATASET) > 0, "Golden Dataset 为空"

    def test_all_questions_have_expected_content(self):
        """每个 QA 对至少要有 expected_keywords 或 expected_content"""
        for i, qa in enumerate(GOLDEN_DATASET):
            assert qa.expected_keywords or qa.expected_content, \
                f"第 {i+1} 个 QA 对缺少 expected_keywords 和 expected_content"

    def test_dataset_stats(self):
        """数据集统计信息应合理"""
        stats = get_dataset_stats()
        assert stats["total"] == len(GOLDEN_DATASET)
        for diff in ["easy", "medium", "hard"]:
            assert diff in stats["by_difficulty"]


# ============================================================
# MOCK 模式测试: 验证评测框架本身的逻辑正确性
# 不依赖任何外部服务，CI 可跑
# ============================================================

class TestRetrievalEvaluationMock:
    """
    MOCK 模式检索评测
    使用模拟 EmbeddingService 和模拟 Milvus。
    验证评测框架的计算逻辑正确。
    """

    @pytest.mark.mock
    def test_mock_evaluator_runs_all_questions(self, mock_evaluator, golden_dataset):
        """MOCK 模式下评测器应能处理所有 QA 对"""
        results = mock_evaluator.evaluate(golden_dataset)
        assert len(results) == len(golden_dataset)

    @pytest.mark.mock
    def test_mock_evaluator_all_pass(self, mock_evaluator):
        """
        MOCK 模式下所有有 expected_keywords 的用例应通过。
        （模拟检索总是返回包含所有关键词的结果）
        """
        dataset = [qa for qa in GOLDEN_DATASET if qa.expected_keywords]
        results = mock_evaluator.evaluate(dataset)
        for r in results:
            assert r.passed, f"Mock 模式下应通过: {r.question[:50]}"

    @pytest.mark.mock
    def test_mock_evaluator_report(self, mock_evaluator):
        """应能生成评测报告"""
        results = mock_evaluator.evaluate()
        mock_evaluator.print_report(results)
        assert len(results) > 0

    @pytest.mark.mock
    def test_mock_evaluator_metrics(self, mock_evaluator):
        """MOCK 模式下的指标应合理"""
        results = mock_evaluator.evaluate()
        for r in results:
            assert 0.0 <= r.recall <= 1.0
            assert 0.0 <= r.precision <= 1.0


# ============================================================
# REAL 模式测试: 连接真实 Milvus + Embedding API
# 需要：Milvus 运行中、Embedding API 可用、文档已上传
# 被 pytest.mark.real 标记，默认不启用
# ============================================================

class TestRetrievalEvaluationReal:
    """
    真实检索评测
    需要 Milvus + Embedding API + 文档已入库。
    默认跳过——需要显式用 -m real 启用。
    """

    @pytest.mark.real
    def test_real_evaluator_all_questions(self, real_evaluator, golden_dataset):
        """REAL 模式下所有 QA 对都应跑完"""
        results = real_evaluator.evaluate(golden_dataset)
        assert len(results) == len(golden_dataset)

    @pytest.mark.real
    def test_real_evaluator_high_recall(self, real_evaluator):
        """REAL 模式下 easy 难度的检索召回率应较高"""
        easy_questions = get_questions_by_difficulty("easy")
        results = real_evaluator.evaluate(easy_questions)
        avg_recall = sum(r.recall for r in results) / len(results) if results else 0
        assert avg_recall > 0.20, f"Easy 问题 avg_recall={avg_recall:.3f} 过低"

    @pytest.mark.real
    def test_real_evaluator_report(self, real_evaluator):
        """生成真实检索评测报告"""
        results = real_evaluator.evaluate()
        real_evaluator.print_report(results)


# ============================================================
# 便捷入口: 直接 python 运行可见报告
# ============================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"D:\Python Project\CampusAsk-RAG\backend")
    
    print("运行 MOCK 模式检索评测...")
    from evaluation.retrieval_evaluator import RetrievalEvaluator
    evaluator = RetrievalEvaluator(top_k=5, use_mock=True)
    results = evaluator.evaluate()
    evaluator.print_report(results)
    
    print("\n\n数据集统计:")
    stats = get_dataset_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
