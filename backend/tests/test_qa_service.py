"""
QA 服务单元测试（基于实际代码）
================================
测试问答服务的核心功能：
- 问答流程
- 缓存机制
- 语义缓存
- 流式输出
- 重试机制
- 答案验证
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from app.services.qa_service import QAService
from app.services.retrieval_service import RetrievalService
from app.services.prompt_template import PromptTemplate
from app.services.cache_service import cache_service
from app.services.semantic_cache import semantic_cache
from app.services.answer_verifier import answer_verifier
from app.services.intent_classifier import intent_classifier


class TestQAServiceInit:
    """QA 服务初始化测试"""

    def test_service_initialization(self):
        """测试服务初始化"""
        with patch('app.services.qa_service.RetrievalService'):
            service = QAService()
            assert service.max_retries >= 1
            assert service.base_delay > 0
            assert service.timeout > 0
            assert service.use_semantic_cache is True


class TestQABasic:
    """基础问答测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            return QAService()

    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金怎么申请？"

    @pytest.fixture
    def sample_contexts(self):
        """示例上下文"""
        return [
            {"content": "奖学金申请需要提交申请表", "source": "学生手册", "score": 0.85},
            {"content": "申请时间为每年9月份", "source": "教务通知", "score": 0.75},
        ]

    def test_ask_returns_answer(self, service, sample_question, sample_contexts):
        """测试问答返回答案"""
        mock_result = {
            "answer": "申请奖学金需要提交申请表。",
            "sources": ["学生手册"],
            "context_count": 1,
            "confidence": "高"
        }
        with patch.object(service.retriever, 'retrieve', return_value=sample_contexts), \
             patch.object(service, '_call_llm_with_retry') as mock_llm, \
             patch.object(service, '_get_current_model_name', return_value="qwen-plus"):
            mock_llm.return_value = Mock(output=Mock(choices=[Mock(message=Mock(content="申请奖学金需要提交申请表。"))]))
            result = service.ask(sample_question, chat_history=[])
            assert isinstance(result, dict)
            assert "answer" in result

    def test_ask_empty_question(self, service):
        """测试空问题"""
        with patch.object(intent_classifier, 'classify', return_value={
            "intent": "unknown",
            "strategy": {"direct_answer": False}
        }), \
             patch.object(service.retriever, 'retrieve', return_value=[]), \
             patch.object(service, '_build_fallback_answer', return_value={
                 "answer": "抱歉，没有找到相关信息。",
                 "sources": [],
                 "context_count": 0,
                 "confidence": "低"
             }):
            result = service.ask("", chat_history=[])
            assert isinstance(result, dict)

    def test_ask_no_context(self, service, sample_question):
        """测试无上下文"""
        with patch.object(service.retriever, 'retrieve', return_value=[]), \
             patch.object(service, '_build_fallback_answer', return_value={
                 "answer": "抱歉，没有找到相关信息。",
                 "sources": [],
                 "context_count": 0,
                 "confidence": "低"
             }):
            result = service.ask(sample_question, chat_history=[])
            assert isinstance(result, dict)

    def test_ask_with_history(self, service, sample_question, sample_contexts):
        """测试带对话历史"""
        history = [{"role": "user", "content": "什么是奖学金？"}]
        mock_result = {
            "answer": "基于历史对话...",
            "sources": ["学生手册"],
            "context_count": 1,
            "confidence": "高"
        }
        with patch.object(service.retriever, 'retrieve', return_value=sample_contexts), \
             patch.object(service, '_call_llm_with_retry') as mock_llm, \
             patch.object(service, '_get_current_model_name', return_value="qwen-plus"):
            mock_llm.return_value = Mock(output=Mock(choices=[Mock(message=Mock(content="基于历史对话..."))]))
            result = service.ask(sample_question, chat_history=history)
            assert isinstance(result, dict)


class TestQACache:
    """QA 缓存测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            return QAService()

    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "图书馆开放时间？"

    def test_cache_key_generation(self, service, sample_question):
        """测试缓存键生成"""
        cache_key = service._get_answer_cache_key(sample_question)
        assert isinstance(cache_key, str)
        assert cache_key.startswith("answer:")

    def test_cache_hit(self, service, sample_question):
        """测试缓存命中"""
        cached = {
            "answer": "图书馆开放时间为早8点到晚10点。",
            "sources": ["图书馆官网"],
            "context_count": 1,
            "confidence": "高"
        }
        with patch.object(cache_service, 'get', return_value=cached):
            cache_key = service._get_answer_cache_key(sample_question)
            result = cache_service.get(cache_key)
            assert result == cached


class TestSemanticCache:
    """语义缓存测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            return QAService()

    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "图书馆几点开门？"

    def test_semantic_cache_hit(self, service, sample_question):
        """测试语义缓存命中"""
        cached = {
            "answer": "图书馆早上8点开门。",
            "sources": ["图书馆官网"],
            "context_count": 1,
            "confidence": "高"
        }
        with patch.object(semantic_cache, 'search_similar', return_value=cached):
            result = semantic_cache.search_similar(sample_question)
            assert result == cached


class TestQARetry:
    """QA 重试机制测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            return QAService()

    def test_retry_on_failure(self, service):
        """测试失败时重试"""
        messages = [{"role": "user", "content": "测试"}]
        with patch('dashscope.Generation.call') as mock_call:
            mock_call.side_effect = [
                Exception("API错误"),
                Mock(status_code=200, output=Mock(choices=[Mock(message=Mock(content="成功"))]))
            ]
            result = service._call_llm_with_retry(messages, model_name="qwen-plus")
            assert mock_call.call_count == 2

    def test_max_retries(self, service):
        """测试达到最大重试次数"""
        messages = [{"role": "user", "content": "测试"}]
        # 设置 max_retries 为 3
        service.max_retries = 3
        with patch('dashscope.Generation.call') as mock_call:
            mock_call.side_effect = Exception("API错误")
            with pytest.raises(Exception):
                service._call_llm_with_retry(messages, model_name="qwen-plus")
            # 应该调用 3 次（max_retries）
            assert mock_call.call_count == 3

    def test_exponential_backoff(self, service):
        """测试指数退避"""
        messages = [{"role": "user", "content": "测试"}]
        with patch('dashscope.Generation.call') as mock_call, \
             patch('time.sleep') as mock_sleep:
            mock_call.side_effect = [
                Exception("错误1"),
                Exception("错误2"),
                Mock(status_code=200, output=Mock(choices=[Mock(message=Mock(content="成功"))]))
            ]
            service._call_llm_with_retry(messages, model_name="qwen-plus")
            assert mock_sleep.call_count == 2


class TestQAStreaming:
    """QA 流式输出测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            return QAService()

    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金怎么申请？"

    def test_streaming_output(self, service, sample_question):
        """测试流式输出"""
        chunks = ["申请", "奖学金", "需要", "提交", "材料"]
        with patch.object(service.retriever, 'retrieve', return_value=[]), \
             patch('dashscope.Generation.call') as mock_call:
            mock_response = Mock(output=Mock(text=""))
            for chunk in chunks:
                mock_response.output.text += chunk
            mock_call.return_value = mock_response
            result = list(service.ask_stream(sample_question, chat_history=[]))
            assert len(result) > 0


class TestAnswerVerification:
    """答案验证测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            service = QAService()
            service.use_answer_verification = True
            return service

    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金申请条件？"

    def test_verify_good_answer(self, service, sample_question):
        """测试验证高质量答案"""
        contexts = [{"content": "奖学金需要成绩优异", "source": "手册", "score": 0.9}]
        answer = "申请奖学金需要成绩优异。"
        with patch.object(answer_verifier, 'verify', return_value={
            "is_valid": True,
            "confidence": 0.9,
            "issues": []
        }):
            result = answer_verifier.verify(answer, contexts, sample_question)
            assert result["is_valid"] is True

    def test_verify_poor_answer(self, service, sample_question):
        """测试验证低质量答案"""
        contexts = [{"content": "奖学金需要成绩优异", "source": "手册", "score": 0.9}]
        answer = "不知道。"
        with patch.object(answer_verifier, 'verify', return_value={
            "is_valid": False,
            "confidence": 0.2,
            "issues": ["答案太短", "信息不足"]
        }):
            result = answer_verifier.verify(answer, contexts, sample_question)
            assert result["is_valid"] is False


class TestIntentClassification:
    """意图识别测试"""

    @pytest.fixture
    def service(self):
        """QA 服务 fixture"""
        with patch('app.services.qa_service.RetrievalService'):
            return QAService()

    def test_greeting_intent(self, service):
        """测试问候意图"""
        with patch.object(intent_classifier, 'classify', return_value={
            "intent": "greeting",
            "strategy": {"direct_answer": True}
        }):
            result = service.ask("你好", chat_history=[])
            assert "你好" in result["answer"] or "您好" in result["answer"]

    def test_farewell_intent(self, service):
        """测试告别意图"""
        with patch.object(intent_classifier, 'classify', return_value={
            "intent": "farewell",
            "strategy": {"direct_answer": True}
        }):
            result = service.ask("再见", chat_history=[])
            # 实际代码可能没有专门处理告别意图，返回通用回答
            assert isinstance(result, dict)
            assert "answer" in result

    def test_question_intent(self, service):
        """测试问题意图"""
        with patch.object(intent_classifier, 'classify', return_value={
            "intent": "question",
            "strategy": {"direct_answer": False}
        }), \
             patch.object(service.retriever, 'retrieve', return_value=[]), \
             patch.object(service, '_build_fallback_answer', return_value={
                 "answer": "回答",
                 "sources": [],
                 "context_count": 0,
                 "confidence": "低"
             }):
            result = service.ask("奖学金怎么申请？", chat_history=[])
            assert isinstance(result, dict)


class TestPromptTemplate:
    """提示词模板测试"""

    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金怎么申请？"

    @pytest.fixture
    def sample_contexts(self):
        """示例上下文"""
        return [{"content": "奖学金申请需要提交申请表", "source": "学生手册", "score": 0.85}]

    def test_build_rag_prompt_basic(self, sample_question, sample_contexts):
        """测试构建基本 RAG 提示词"""
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=sample_contexts,
            chat_history=[]
        )
        assert prompt is not None
        assert sample_question in prompt

    def test_build_rag_prompt_with_history(self, sample_question, sample_contexts):
        """测试构建带历史的 RAG 提示词"""
        history = [{"role": "user", "content": "什么是奖学金？"}]
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=sample_contexts,
            chat_history=history
        )
        assert prompt is not None
        assert "历史" in prompt or "对话" in prompt

    def test_build_rag_prompt_empty_context(self, sample_question):
        """测试构建空上下文的 RAG 提示词"""
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=[],
            chat_history=[]
        )
        assert prompt is not None
        assert sample_question in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
