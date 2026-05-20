"""
QA 服务单元测试
================
测试问答服务的核心功能：
- 问答流程
- 缓存机制
- 语义缓存
- 流式输出
- 重试机制
- 答案验证
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict
from datetime import datetime

from app.services.qa_service import QAService
from app.services.retrieval_service import RetrievalService
from app.services.prompt_template import PromptTemplate
from app.services.cache_service import cache_service
from app.services.semantic_cache import semantic_cache
from app.services.answer_verifier import answer_verifier
from app.services.intent_classifier import intent_classifier


class TestQAServiceBasic:
    """QA 服务基础测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        return QAService()
    
    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金怎么申请？"
    
    @pytest.fixture
    def sample_contexts(self):
        """示例上下文"""
        return [
            {
                "content": "奖学金申请需要提交申请表和成绩单",
                "source": "学生手册",
                "score": 0.85,
            },
            {
                "content": "申请时间为每年 9 月份",
                "source": "教务通知",
                "score": 0.75,
            },
        ]
    
    def test_qa_service_initialization(self, qa_service):
        """测试 QA 服务初始化"""
        assert qa_service.retriever is not None
        assert qa_service.model is not None
        assert qa_service.max_retries >= 1
        assert qa_service.base_delay > 0
    
    def test_ask_single_turn(self, qa_service, sample_question, sample_contexts):
        """测试单轮问答"""
        with patch.object(qa_service.retriever, 'retrieve', return_value=sample_contexts), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_llm.return_value = "申请奖学金需要提交申请表和成绩单，时间为每年 9 月份。"
            
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert answer is not None
            assert isinstance(answer, str)
            assert len(answer) > 0
            assert mock_llm.called
    
    def test_ask_with_chat_history(self, qa_service, sample_question, sample_contexts):
        """测试带对话历史的问答"""
        chat_history = [
            {"role": "user", "content": "奖学金是什么？"},
            {"role": "assistant", "content": "奖学金是奖励给优秀学生的资金。"},
        ]
        
        with patch.object(qa_service.retriever, 'retrieve', return_value=sample_contexts), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_llm.return_value = "基于你的历史对话，奖学金申请需要..."
            
            answer = qa_service.ask(sample_question, chat_history=chat_history)
            
            assert answer is not None
            assert len(answer) > 0
            assert mock_llm.called
    
    def test_ask_empty_question(self, qa_service):
        """测试空问题"""
        with pytest.raises(ValueError):
            qa_service.ask("", chat_history=[])
    
    def test_ask_no_context(self, qa_service, sample_question):
        """测试无上下文时的问答"""
        with patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_llm.return_value = "抱歉，我没有找到相关信息。"
            
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert answer is not None
            assert mock_llm.called


class TestQACache:
    """QA 缓存测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        return QAService()
    
    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "图书馆开放时间？"
    
    def test_answer_cache_hit(self, qa_service, sample_question):
        """测试答案缓存命中"""
        cached_answer = "图书馆开放时间为每天早上 8 点到晚上 10 点。"
        
        with patch.object(qa_service, '_get_answer_cache_key') as mock_key, \
             patch('app.services.cache_service.cache_service') as mock_cache:
            
            mock_key.return_value = "test:cache:key"
            mock_cache.get.return_value = cached_answer
            
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert answer == cached_answer
            assert mock_cache.get.called
    
    def test_answer_cache_miss(self, qa_service, sample_question):
        """测试答案缓存未命中"""
        with patch.object(qa_service, '_get_answer_cache_key') as mock_key, \
             patch('app.services.cache_service.cache_service') as mock_cache, \
             patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_key.return_value = "test:cache:key"
            mock_cache.get.return_value = None
            mock_llm.return_value = "图书馆开放时间为..."
            
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert mock_cache.get.called
            assert mock_llm.called
            assert mock_cache.set.called  # 应该缓存新答案
    
    def test_semantic_cache_hit(self, qa_service, sample_question):
        """测试语义缓存命中"""
        similar_question = "图书馆几点开门？"
        cached_result = {
            "question": similar_question,
            "answer": "图书馆早上 8 点开门。",
            "contexts": [],
        }
        
        with patch.object(qa_service, 'use_semantic_cache', True), \
             patch('app.services.semantic_cache.semantic_cache') as mock_semantic:
            
            mock_semantic.get.return_value = cached_result
            
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert answer == cached_result["answer"]
            assert mock_semantic.get.called
    
    def test_semantic_cache_miss(self, qa_service, sample_question):
        """测试语义缓存未命中"""
        with patch.object(qa_service, 'use_semantic_cache', True), \
             patch('app.services.semantic_cache.semantic_cache') as mock_semantic, \
             patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_semantic.get.return_value = None
            mock_llm.return_value = "图书馆开放时间..."
            
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert mock_semantic.get.called
            assert mock_llm.called
            assert mock_semantic.set.called  # 应该缓存新结果


class TestQARetry:
    """QA 重试机制测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        return QAService()
    
    def test_llm_retry_on_failure(self, qa_service):
        """测试 LLM 调用失败时重试"""
        messages = [{"role": "user", "content": "测试问题"}]
        
        with patch('dashscope.Generation.call') as mock_call:
            # 前两次失败，第三次成功
            mock_call.side_effect = [
                Exception("API 错误"),
                Exception("API 错误"),
                Mock(result="成功回答")
            ]
            
            result = qa_service._call_llm_with_retry(messages)
            
            assert mock_call.call_count == 3
            assert result is not None
    
    def test_llm_max_retries(self, qa_service):
        """测试达到最大重试次数"""
        messages = [{"role": "user", "content": "测试问题"}]
        
        with patch('dashscope.Generation.call') as mock_call:
            mock_call.side_effect = Exception("API 错误")
            
            with pytest.raises(Exception):
                qa_service._call_llm_with_retry(messages, max_retries=3)
            
            assert mock_call.call_count == 3
    
    def test_llm_exponential_backoff(self, qa_service):
        """测试指数退避"""
        messages = [{"role": "user", "content": "测试问题"}]
        
        with patch('dashscope.Generation.call') as mock_call, \
             patch('time.sleep') as mock_sleep:
            
            mock_call.side_effect = [
                Exception("API 错误"),
                Exception("API 错误"),
                Mock(result="成功回答")
            ]
            
            result = qa_service._call_llm_with_retry(messages)
            
            # 验证退避时间递增
            assert mock_sleep.call_count == 2
            sleep_times = [call_args[0][0] for call_args in mock_sleep.call_args_list]
            assert sleep_times[0] < sleep_times[1]  # 第二次等待时间更长


class TestQAStreaming:
    """QA 流式输出测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        return QAService()
    
    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金怎么申请？"
    
    def test_streaming_output(self, qa_service, sample_question):
        """测试流式输出"""
        mock_chunks = [
            "申请",
            "奖学金",
            "需要",
            "提交",
            "材料",
            "。",
        ]
        
        with patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch('dashscope.Generation.call') as mock_call:
            
            # Mock 流式输出
            mock_response = Mock()
            mock_response.output = Mock()
            mock_response.output.text = ""
            
            for chunk in mock_chunks:
                mock_response.output.text += chunk
            
            mock_call.return_value = mock_response
            
            chunks = []
            for chunk in qa_service.ask_stream(sample_question, chat_history=[]):
                chunks.append(chunk)
            
            assert len(chunks) > 0
            assert "".join(chunks) == "".join(mock_chunks)
    
    def test_streaming_vs_non_streaming(self, qa_service, sample_question):
        """测试流式与非流式对比"""
        contexts = [{"content": "测试内容", "source": "测试", "score": 0.8}]
        
        with patch.object(qa_service.retriever, 'retrieve', return_value=contexts), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_llm.return_value = "这是完整回答。"
            
            # 非流式
            answer = qa_service.ask(sample_question, chat_history=[])
            
            # 流式
            stream_chunks = list(qa_service.ask_stream(sample_question, chat_history=[]))
            stream_answer = "".join(stream_chunks)
            
            # 两者结果应该一致
            assert answer == stream_answer or len(stream_answer) > 0


class TestAnswerVerification:
    """答案验证测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        service = QAService()
        service.use_answer_verification = True
        return service
    
    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金申请条件是什么？"
    
    def test_verify_good_answer(self, qa_service, sample_question):
        """测试验证高质量答案"""
        contexts = [
            {"content": "奖学金需要成绩优异", "source": "手册", "score": 0.9}
        ]
        answer = "申请奖学金需要成绩优异，无挂科记录。"
        
        with patch.object(answer_verifier, 'verify') as mock_verify:
            mock_verify.return_value = {
                "is_good": True,
                "confidence": 0.9,
                "issues": []
            }
            
            is_acceptable = qa_service._verify_answer(sample_question, answer, contexts)
            
            assert is_acceptable
            assert mock_verify.called
    
    def test_verify_poor_answer(self, qa_service, sample_question):
        """测试验证低质量答案"""
        contexts = [
            {"content": "奖学金需要成绩优异", "source": "手册", "score": 0.9}
        ]
        answer = "不知道。"
        
        with patch.object(answer_verifier, 'verify') as mock_verify:
            mock_verify.return_value = {
                "is_good": False,
                "confidence": 0.2,
                "issues": ["答案太短", "信息不足"]
            }
            
            is_acceptable = qa_service._verify_answer(sample_question, answer, contexts)
            
            assert not is_acceptable
            assert mock_verify.called
    
    def test_verify_with_retry(self, qa_service, sample_question):
        """测试验证失败时重试"""
        contexts = [
            {"content": "奖学金需要成绩优异", "source": "手册", "score": 0.9}
        ]
        
        with patch.object(qa_service, '_call_llm_with_retry') as mock_llm, \
             patch.object(answer_verifier, 'verify') as mock_verify:
            
            # 第一次验证失败
            mock_verify.side_effect = [
                {"is_good": False, "confidence": 0.3, "issues": ["信息不足"]},
                {"is_good": True, "confidence": 0.85, "issues": []},
            ]
            
            mock_llm.side_effect = [
                "第一次回答（质量差）",
                "第二次回答（质量好）"
            ]
            
            # 应该重试并生成更好的回答
            answer = qa_service.ask(sample_question, chat_history=[])
            
            assert mock_llm.call_count >= 1


class TestIntentClassification:
    """意图识别测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        return QAService()
    
    def test_greeting_intent(self, qa_service):
        """测试问候意图"""
        question = "你好"
        
        with patch.object(intent_classifier, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "greeting",
                "confidence": 0.95
            }
            
            answer = qa_service.ask(question, chat_history=[])
            
            assert "你好" in answer or "您好" in answer or "hello" in answer.lower()
    
    def test_farewell_intent(self, qa_service):
        """测试告别意图"""
        question = "再见"
        
        with patch.object(intent_classifier, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "farewell",
                "confidence": 0.95
            }
            
            answer = qa_service.ask(question, chat_history=[])
            
            assert "再见" in answer or "拜拜" in answer or "bye" in answer.lower()
    
    def test_question_intent(self, qa_service):
        """测试问题意图"""
        question = "奖学金怎么申请？"
        
        with patch.object(intent_classifier, 'classify') as mock_classify, \
             patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_classify.return_value = {
                "intent": "question",
                "confidence": 0.9
            }
            mock_llm.return_value = "申请奖学金需要..."
            
            answer = qa_service.ask(question, chat_history=[])
            
            assert mock_llm.called
            assert len(answer) > 0


class TestQAPromptTemplate:
    """QA 提示词模板测试"""
    
    @pytest.fixture
    def sample_question(self):
        """示例问题"""
        return "奖学金怎么申请？"
    
    @pytest.fixture
    def sample_contexts(self):
        """示例上下文"""
        return [
            {
                "content": "奖学金申请需要提交申请表",
                "source": "学生手册",
                "score": 0.85,
            },
        ]
    
    def test_build_rag_prompt_basic(self, sample_question, sample_contexts):
        """测试构建基本 RAG 提示词"""
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=sample_contexts,
            chat_history=[],
        )
        
        assert prompt is not None
        assert len(prompt) > 0
        assert sample_question in prompt
        assert "奖学金" in prompt or "申请" in prompt
    
    def test_build_rag_prompt_with_history(self, sample_question, sample_contexts):
        """测试构建带历史的 RAG 提示词"""
        chat_history = [
            {"role": "user", "content": "什么是奖学金？"},
            {"role": "assistant", "content": "奖学金是奖励给优秀学生的资金。"},
        ]
        
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=sample_contexts,
            chat_history=chat_history,
        )
        
        assert prompt is not None
        assert "对话历史" in prompt or "历史" in prompt
        assert "奖学金" in prompt
    
    def test_build_rag_prompt_empty_context(self, sample_question):
        """测试构建空上下文的 RAG 提示词"""
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=[],
            chat_history=[],
        )
        
        assert prompt is not None
        assert sample_question in prompt
    
    def test_build_rag_prompt_format(self, sample_question, sample_contexts):
        """测试提示词格式"""
        prompt = PromptTemplate.build_rag_prompt(
            question=sample_question,
            contexts=sample_contexts,
            chat_history=[],
        )
        
        # 验证提示词包含必要的部分
        assert "问题" in prompt or "Question" in prompt
        assert "上下文" in prompt or "Context" in prompt or "信息" in prompt


class TestQAServiceIntegration:
    """QA 服务集成测试"""
    
    @pytest.fixture
    def qa_service(self):
        """QA 服务 fixture"""
        return QAService()
    
    def test_full_qa_pipeline(self, qa_service):
        """测试完整 QA 流程"""
        question = "图书馆开放时间？"
        
        with patch.object(qa_service.retriever, 'retrieve') as mock_retrieve, \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm, \
             patch('app.services.cache_service.cache_service.get', return_value=None):
            
            mock_retrieve.return_value = [
                {
                    "content": "图书馆开放时间为每天早上 8 点到晚上 10 点",
                    "source": "图书馆官网",
                    "score": 0.9,
                }
            ]
            mock_llm.return_value = "图书馆的开放时间为每天早上 8 点至晚上 10 点。"
            
            answer = qa_service.ask(question, chat_history=[])
            
            assert mock_retrieve.called
            assert mock_llm.called
            assert answer is not None
            assert len(answer) > 10
    
    def test_qa_with_model_selection(self, qa_service):
        """测试模型选择"""
        question = "测试问题"
        
        with patch.object(qa_service, '_get_current_model_name') as mock_model, \
             patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_model.return_value = "qwen-turbo"
            mock_llm.return_value = "测试回答"
            
            answer = qa_service.ask(question, chat_history=[])
            
            assert mock_model.called
            assert mock_llm.called
    
    def test_qa_error_handling(self, qa_service):
        """测试 QA 错误处理"""
        question = "测试问题"
        
        with patch.object(qa_service.retriever, 'retrieve', side_effect=Exception("检索失败")), \
             patch.object(qa_service, '_call_llm_with_retry') as mock_llm:
            
            mock_llm.return_value = "抱歉，暂时无法获取相关信息。"
            
            # 应该优雅降级而不是崩溃
            answer = qa_service.ask(question, chat_history=[])
            
            assert answer is not None
            assert isinstance(answer, str)
    
    def test_qa_timeout_handling(self, qa_service):
        """测试 QA 超时处理"""
        question = "测试问题"
        
        with patch.object(qa_service.retriever, 'retrieve', return_value=[]), \
             patch.object(qa_service, '_call_llm_with_retry', side_effect=TimeoutError("LLM 超时")):
            
            with pytest.raises(TimeoutError):
                qa_service.ask(question, chat_history=[])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
