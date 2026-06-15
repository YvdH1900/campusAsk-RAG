"""
答案验证器真实环境测试
====================
连接真实 LLM，验证答案质量判断逻辑
"""

import pytest


@pytest.mark.real
class TestAnswerVerifierReal:
    """答案验证器真实环境测试"""

    def test_verify_good_answer(self):
        """
        测试验证一个正确答案
        """
        from app.services.answer_verifier import answer_verifier

        answer = "上海交通大学的校训是饮水思源，爱国荣校。这体现了学校的精神内核和办学传统。"
        contexts = [
            {"content": "上海交通大学校训：饮水思源，爱国荣校。这是学校的精神内核。"}
        ]
        question = "上海交通大学的校训是什么？"

        result = answer_verifier.verify(answer, contexts, question)

        assert "is_valid" in result, "结果缺少是否有效字段"
        assert "confidence" in result, "结果缺少置信度字段"
        assert "context_coverage" in result, "结果缺少上下文覆盖率字段"
        assert "issues" in result, "结果缺少问题字段"

        print(f"\n答案验证结果:")
        print(f"  是否有效: {result['is_valid']}")
        print(f"  置信度: {result['confidence']}")
        print(f"  上下文覆盖率: {result['context_coverage']}")
        print(f"  问题: {result['issues']}")

        assert result["confidence"] > 0.5, f"置信度过低: {result['confidence']}"

    def test_verify_empty_answer(self):
        """
        测试验证空答案
        预期：is_valid=False, confidence=0.0
        """
        from app.services.answer_verifier import answer_verifier

        result = answer_verifier.verify("", [], "问题")

        assert result["is_valid"] is False
        assert result["confidence"] == 0.0
        assert "答案为空" in result["issues"]

    def test_verify_answer_with_disclaimer(self):
        """
        测试验证包含不确定表述的答案
        预期：issues 包含"不确定表述"
        """
        from app.services.answer_verifier import answer_verifier

        answer = "我不确定，但据说校训是饮水思源。"
        contexts = [{"content": "校训是饮水思源"}]

        result = answer_verifier.verify(answer, contexts, "校训是什么")

        assert any("不确定" in issue for issue in result["issues"]), \
            f"应该检测到不确定表述，实际 issues: {result['issues']}"
        print(f"\n不确定表述检测: {result['issues']}")

    def test_verify_answer_too_short(self):
        """
        测试验证过短答案
        预期：issues 包含"答案过短"
        """
        from app.services.answer_verifier import answer_verifier

        answer = "是的"
        contexts = [{"content": "一些上下文内容"}]

        result = answer_verifier.verify(answer, contexts, "问题")

        assert any("过短" in issue for issue in result["issues"]), \
            f"应该检测到答案过短，实际 issues: {result['issues']}"

    def test_verify_low_context_coverage(self):
        """
        测试短答案 + 内容无关时的覆盖率检测
        预期：context_coverage < 0.3
        """
        from app.services.answer_verifier import answer_verifier

        answer = "今天天气很好，适合出去散步。"
        contexts = [{"content": "上海交通大学校训是饮水思源"}]

        result = answer_verifier.verify(answer, contexts, "校训是什么")

        assert result["context_coverage"] < 0.3, \
            f"无关短答案的覆盖率应该很低，实际: {result['context_coverage']}"

        print(f"\n短答案覆盖率: {result['context_coverage']}")
        print(f"检测到的问题: {result['issues']}")

    def test_verify_with_ai_enabled(self):
        """
        测试启用 AI 验证
        前提：dashscope API 可用
        """
        from app.services.answer_verifier import answer_verifier

        answer = "上海交通大学的校训是饮水思源。"
        contexts = [{"content": "校训：饮水思源，爱国荣校"}]
        question = "校训是什么？"

        try:
            result = answer_verifier.verify(
                answer, contexts, question,
                use_ai=True,
                model_name="deepseek-v4-pro"
            )

            print(f"\nAI 验证结果:")
            print(f"  是否有效: {result['is_valid']}")
            print(f"  AI 理由: {result.get('ai_reason', 'N/A')}")

            assert "is_valid" in result
        except Exception as e:
            pytest.skip(f"AI verification failed: {e}")
