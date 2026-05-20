"""
对话摘要服务
============
对过长的对话历史进行摘要压缩
减少 token 消耗，保留关键信息
支持两种模式：
1. AI 摘要：使用 LLM 生成对话摘要（效果更好，保留语义）
2. 截断模式：基于 Token 估算截断最早消息（fallback，零成本）
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SummaryService:
    """对话摘要服务"""

    MAX_HISTORY_TOKENS = 1500
    AVG_CHARS_PER_TOKEN = 2

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """
        估算文本的 token 数量
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数量
        """
        return len(text) // cls.AVG_CHARS_PER_TOKEN

    @classmethod
    def compress_history(
        cls,
        chat_history: List[Dict],
        max_tokens: Optional[int] = None,
        use_ai: bool = False,
        model_name: str = "qwen-plus",
    ) -> List[Dict]:
        """
        压缩对话历史
        
        Args:
            chat_history: 原始对话历史
            max_tokens: 最大 token 数量
            use_ai: 是否使用 AI 摘要
            model_name: AI 摘要使用的 LLM 模型名称
            
        Returns:
            压缩后的对话历史
        """
        max_tokens = max_tokens or cls.MAX_HISTORY_TOKENS
        
        if not chat_history:
            return []

        total_tokens = sum(
            cls.estimate_tokens(msg.get("content", ""))
            for msg in chat_history
        )

        if total_tokens <= max_tokens:
            return chat_history

        if use_ai:
            return cls._ai_compress(chat_history, max_tokens, model_name)
        else:
            return cls._truncate_compress(chat_history, max_tokens)

    @classmethod
    def _truncate_compress(
        cls,
        chat_history: List[Dict],
        max_tokens: int,
    ) -> List[Dict]:
        """基于截断的压缩（fallback 模式）"""
        compressed = []
        current_tokens = 0
        
        for msg in reversed(chat_history):
            msg_tokens = cls.estimate_tokens(msg.get("content", ""))
            if current_tokens + msg_tokens <= max_tokens:
                compressed.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break

        logger.info(
            f"截断压缩: {len(chat_history)} 条 -> {len(compressed)} 条 "
            f"({sum(cls.estimate_tokens(m.get('content', '')) for m in chat_history)} tokens -> {current_tokens} tokens)"
        )
        
        return compressed

    @classmethod
    def _ai_compress(
        cls,
        chat_history: List[Dict],
        max_tokens: int,
        model_name: str = "qwen-plus",
    ) -> List[Dict]:
        """使用 LLM 进行对话摘要压缩"""
        try:
            history_text = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in chat_history
            )
            
            prompt = (
                f"请将以下对话历史压缩为简洁的摘要，保留关键信息和上下文，"
                f"以便后续对话能理解之前的讨论内容。摘要控制在 200 字以内。\n\n"
                f"对话历史：\n{history_text}"
            )
            
            from dashscope import Generation
            response = Generation.call(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                result_format="message",
                temperature=0.3,
                max_tokens=300,
            )
            
            if response.status_code == 200:
                summary = response.output.choices[0].message.content.strip()
                
                summary_msg = {
                    "role": "system",
                    "content": f"[对话历史摘要] {summary}",
                }
                
                logger.info(f"AI 对话摘要: {len(chat_history)} 条 -> 1 条摘要")
                return [summary_msg]
            
            logger.warning("AI 摘要失败，降级到截断压缩")
        except Exception as e:
            logger.warning(f"AI 摘要异常: {e}，降级到截断压缩")
        
        return cls._truncate_compress(chat_history, max_tokens)

    @classmethod
    def should_compress(cls, chat_history: List[Dict]) -> bool:
        """
        判断是否需要压缩对话历史
        
        Args:
            chat_history: 对话历史
            
        Returns:
            是否需要压缩
        """
        total_tokens = sum(
            cls.estimate_tokens(msg.get("content", ""))
            for msg in chat_history
        )
        need = total_tokens > cls.MAX_HISTORY_TOKENS
        if len(chat_history) > 0:
            logger.info(f"对话压缩检查: {len(chat_history)}条消息, {total_tokens}/{cls.MAX_HISTORY_TOKENS} tokens, 需要压缩={need}")
        return need
