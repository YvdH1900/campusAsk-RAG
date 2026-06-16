
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
from .golden_dataset import (
    GOLDEN_DATASET, get_dataset_stats, get_questions_by_difficulty,
    validate_against_document,
)


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

    def test_golden_dataset_against_document(self):
        """
        验证 Golden Dataset 中的关键词/内容确实存在于学生手册文档中。
        这是确保评测有效的关键测试——如果关键词不在文档中，检索永远无法命中。
        """
        result = validate_against_document(verbose=True)
        
        if "error" in result:
            pytest.skip(f"跳过文档一致性验证: {result['error']}")
        
        # 关键词命中率应 >= 95%（允许少量长句拼接导致的不匹配）
        assert result["keyword_hit_rate"] >= 0.95, \
            f"关键词命中率过低: {result['keyword_hit_rate']:.1%}，存在 {len(result['issues'])} 个问题"
        
        # 内容片段命中率应 >= 75%（内容片段较长，可能因标点符号等格式差异不匹配）
        assert result["content_hit_rate"] >= 0.75, \
            f"内容命中率过低: {result['content_hit_rate']:.1%}"
        
        # 打印问题详情帮助诊断
        for issue in result["issues"]:
            print(f"  [警告] #{issue['index']} '{issue['question']}': "
                  f"缺少关键词={issue['missing_keywords']}, "
                  f"缺少内容片段数={len(issue['missing_content'])}")


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
    def test_mock_evaluator_hit_rate_reasonable(self, mock_evaluator):
        """
        MOCK 模式下模拟真实检索行为，命中率应在合理范围。
        - is_hit（至少命中1个关键词）应该在 60%-95% 之间
        - passed（通过严格标准）应在 30%-80% 之间
        """
        dataset = [qa for qa in GOLDEN_DATASET if qa.expected_keywords]
        results = mock_evaluator.evaluate(dataset)
        
        total = len(results)
        hit_count = sum(1 for r in results if r.is_hit)
        passed_count = sum(1 for r in results if r.passed)
        hit_rate = hit_count / total
        pass_rate = passed_count / total
        
        print(f"\n  MOCK 模式: is_hit={hit_count}/{total} ({hit_rate:.1%}), "
              f"passed={passed_count}/{total} ({pass_rate:.1%})")
        
        # 至少命中1个关键词的比例（~20% miss，所以约 70-90%）
        assert 0.65 <= hit_rate <= 0.90, \
            f"is_hit 命中率 {hit_rate:.1%} 不合理（应在 65%-90%）"
        # 通过严格标准（>=2个或>=50%）的比例
        assert 0.20 <= pass_rate <= 0.80, \
            f"pass 通过率 {pass_rate:.1%} 不合理（应在 20%-80%）"

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
    def test_real_evaluator_easy_hit_rate(self, real_evaluator):
        """
        REAL 模式下 easy 难度的检索命中率应较高。
        使用 is_hit（top-k 中至少命中一个关键词）而非 recall，
        因为 recall 依赖于所有关键词都出现，而部分关键词可能在不同 chunk 中。
        """
        easy_questions = get_questions_by_difficulty("easy")
        results = real_evaluator.evaluate(easy_questions)
        
        hit_count = sum(1 for r in results if r.is_hit)
        hit_rate = hit_count / len(results) if results else 0
        
        print(f"\n  Easy 难度命中率: {hit_rate:.1%} ({hit_count}/{len(results)})")
        for r in results:
            if not r.is_hit:
                print(f"    [未命中] {r.question[:50]}")
                if r.missing_keywords:
                    print(f"             缺少关键词: {r.missing_keywords[:3]}")
        
        assert hit_rate >= 0.30, f"Easy 问题命中率 {hit_rate:.1%} 过低，应为 >= 30%"

    @pytest.mark.real
    def test_real_evaluator_overall_pass(self, real_evaluator):
        """
        REAL 模式下总体通过率应达到基本要求。
        通过率 = passed数量 / 总数。
        """
        results = real_evaluator.evaluate()
        
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        pass_rate = passed / total if total else 0
        
        print(f"\n  总体通过率: {pass_rate:.1%} ({passed}/{total})")
        
        # 按难度分解
        for diff in ["easy", "medium", "hard"]:
            diff_results = [r for r in results if r.difficulty == diff]
            if diff_results:
                d_passed = sum(1 for r in diff_results if r.passed)
                d_rate = d_passed / len(diff_results)
                print(f"    [{diff}] {d_rate:.1%} ({d_passed}/{len(diff_results)})")
        
        # 总体通过率 >= 30%
        assert pass_rate >= 0.30, f"总体通过率 {pass_rate:.1%} 过低"

    @pytest.mark.real
    def test_real_evaluator_report(self, real_evaluator):
        """生成真实检索评测报告"""
        results = real_evaluator.evaluate()
        real_evaluator.print_report(results)
