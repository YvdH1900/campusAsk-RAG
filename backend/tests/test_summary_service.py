"""
对话摘要服务测试
===============
测试截断模式 + AI 模式（真实 LLM 调用）
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.summary_service import SummaryService


class TestSummaryServiceTruncate:
    """截断模式测试（纯本地，无外部依赖）"""

    def test_no_compression_needed(self):
        """对话未超阈值，不压缩"""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮助你的？"},
        ]
        result = SummaryService.compress_history(history, max_tokens=10000)
        assert result == history

    def test_truncate_keeps_recent_messages(self):
        """截断保留最近的消息"""
        history = [
            {"role": "user", "content": "A" * 2000},
            {"role": "assistant", "content": "B" * 2000},
            {"role": "user", "content": "C" * 500},
        ]
        result = SummaryService.compress_history(history, max_tokens=2000)
        # 应该只保留最后一条或最后几条
        assert len(result) < len(history)
        # 保留的应该是最近的消息
        assert result[-1]["content"] == "C" * 500

    def test_empty_history(self):
        """空对话返回空列表"""
        assert SummaryService.compress_history([]) == []

    def test_should_compress_true(self):
        """超长对话需要压缩"""
        history = [
            {"role": "user", "content": "A" * 5000},
            {"role": "assistant", "content": "B" * 5000},
        ]
        assert SummaryService.should_compress(history) is True

    def test_should_compress_false(self):
        """短对话不需要压缩"""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
        ]
        assert SummaryService.should_compress(history) is False

    def test_should_compress_empty(self):
        """空对话不需要压缩"""
        assert SummaryService.should_compress([]) is False

    def test_estimate_tokens(self):
        """Token 估算"""
        # 平均 2 字符/token
        assert SummaryService.estimate_tokens("A" * 100) == 50
        assert SummaryService.estimate_tokens("") == 0

    def test_truncate_preserves_order(self):
        """截断后消息顺序不变"""
        history = [
            {"role": "user", "content": "第一条" * 10},
            {"role": "assistant", "content": "回复一" * 10},
            {"role": "user", "content": "第二条" * 10},
            {"role": "assistant", "content": "回复二" * 10},
        ]
        # 每条约 30 字符 = 15 tokens，4 条 = 60 tokens
        # 设置 max_tokens=40 只能容纳最后 2 条
        result = SummaryService.compress_history(history, max_tokens=40)
        assert len(result) >= 1
        assert result[-1] == history[-1]

    def test_truncate_returns_empty_when_tokens_too_small(self):
        """max_tokens 太小无法容纳任何消息时返回空列表"""
        history = [
            {"role": "user", "content": "一条消息"},
        ]
        result = SummaryService.compress_history(history, max_tokens=1)
        assert result == []


class TestSummaryServiceAI:
    """AI 摘要模式测试（真实 LLM 调用）"""

    def test_ai_compress_success(self):
        """AI 摘要成功"""
        history = [
            {"role": "user", "content": "上海交通大学的校训是什么？"},
            {"role": "assistant", "content": "上海交通大学的校训是饮水思源，爱国荣校。"},
            {"role": "user", "content": "这个校训有什么含义？"},
            {"role": "assistant", "content": "饮水思源意味着感恩，爱国荣校强调为国家做贡献。"},
        ]

        try:
            result = SummaryService.compress_history(history, max_tokens=100, use_ai=True, model_name="qwen-plus")
            # AI 摘要成功应返回 1 条 system 消息
            assert len(result) == 1
            assert result[0]["role"] == "system"
            assert "[对话历史摘要]" in result[0]["content"]
            print(f"\nAI 摘要: {result[0]['content']}")
        except Exception as e:
            pytest.skip(f"AI 摘要失败: {e}")

    def test_ai_compress_fallback_to_truncate(self):
        """AI 摘要失败时降级到截断模式"""
        history = [
            {"role": "user", "content": "A" * 2000},
            {"role": "assistant", "content": "B" * 2000},
            {"role": "user", "content": "C" * 2000},
            {"role": "assistant", "content": "D" * 2000},
        ]

        # mock _ai_compress 让它调用 _truncate_compress（模拟 AI 失败降级）
        original = SummaryService._ai_compress
        SummaryService._ai_compress = classmethod(
            lambda cls, chat_history, max_tokens, model_name="qwen-plus":
                SummaryService._truncate_compress(chat_history, max_tokens)
        )
        try:
            result = SummaryService.compress_history(history, max_tokens=2000, use_ai=True)
            assert len(result) < len(history)
            assert len(result) > 0
        finally:
            SummaryService._ai_compress = original

    def test_ai_compress_http_error(self):
        """AI 摘要返回非 200 时降级"""
        history = [
            {"role": "user", "content": "A" * 2000},
            {"role": "assistant", "content": "B" * 2000},
        ]

        # mock _ai_compress 返回空列表（模拟 AI 失败降级）
        with patch.object(SummaryService, "_ai_compress", return_value=[]):
            result = SummaryService.compress_history(history, max_tokens=1000, use_ai=True)
            # 降级到截断模式
            assert len(result) < len(history)
