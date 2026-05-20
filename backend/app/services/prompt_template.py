"""
提示词模板服务（企业级）
======================
构建 RAG 问答的结构化提示词
支持：
- 单轮问答提示词
- 多轮对话提示词（含历史上下文）
- 引用标注要求
- 置信度评估
- 系统提示词（角色设定）
"""

from typing import List, Optional


class PromptTemplate:
    """提示词模板构建器"""

    SYSTEM_PROMPT = """你是一个校园智能助手，专门基于校园知识库为用户提供准确的信息。

你的职责：
1. 仅基于提供的上下文信息回答问题
2. 如果上下文信息不足以回答问题，请明确告知用户
3. 回答要准确、简洁、专业
4. 使用中文回答（除非用户明确要求使用其他语言）
5. 不要编造或推测上下文之外的信息

注意：
- 如果用户的问题与校园无关，请礼貌地引导回校园相关话题
- 如果上下文中存在矛盾信息，请指出并说明来源
- 回答时适当引用来源文档
- 严禁重复相同的内容或句子，每个要点只说一次
- 不要循环引用或反复强调同一信息"""

    @classmethod
    def build_rag_prompt(
        cls,
        question: str,
        contexts: List[dict],
        chat_history: Optional[List[dict]] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """
        构建 RAG 问答提示词
        
        Args:
            question: 用户问题
            contexts: 检索到的上下文信息列表，格式:
                [
                    {
                        "content": "文档内容",
                        "source": "来源文档",
                        "score": 0.85,
                    },
                    ...
                ]
            chat_history: 对话历史（可选），格式:
                [
                    {"role": "user", "content": "问题"},
                    {"role": "assistant", "content": "回答"},
                    ...
                ]
            model_name: 当前使用的模型名称（可选）
                
        Returns:
            完整的提示词字符串
        """
        prompt_parts = []

        # 1. 添加对话历史（如果有）
        if chat_history:
            summary_msgs = [m for m in chat_history if m.get("role") in ("summary", "system")]
            normal_msgs = [m for m in chat_history if m.get("role") not in ("summary", "system")]

            if summary_msgs:
                prompt_parts.append("对话历史摘要：")
                for msg in summary_msgs:
                    prompt_parts.append(msg["content"])
                prompt_parts.append("")

            if normal_msgs:
                prompt_parts.append("最近对话：")
                for msg in normal_msgs[-6:]:
                    role = "用户" if msg["role"] == "user" else "助手"
                    prompt_parts.append(f"{role}: {msg['content']}")
                prompt_parts.append("")

        # 2. 添加上下文信息
        if contexts:
            prompt_parts.append("以下是从校园知识库中检索到的相关信息：")
            prompt_parts.append("=" * 50)
            
            for i, ctx in enumerate(contexts, 1):
                prompt_parts.append(f"[来源 {i}] {ctx.get('source', '未知文档')} (相关度：{ctx.get('score', 0):.2f})")
                prompt_parts.append(ctx["content"])
                prompt_parts.append("-" * 30)
            
            prompt_parts.append("=" * 50)
            prompt_parts.append("")

            # 3. 添加用户问题
            prompt_parts.append(f"请基于以上提供的上下文信息，回答以下问题：")
            prompt_parts.append(f"问题：{question}")
            prompt_parts.append("")
            prompt_parts.append("回答要求：")
            prompt_parts.append("1. 直接回答问题，不要在回答中包含来源标注或置信度信息")
            prompt_parts.append("2. 回答要准确、简洁、专业")
            if model_name:
                prompt_parts.append(f"3. 在回答的最后一行，另起一行标注当前使用的模型名称，格式为：【模型：{model_name}】")
        else:
            # 没有检索到上下文时，让 LLM 基于自身知识回答
            prompt_parts.append(f"用户问题：{question}")
            prompt_parts.append("")
            prompt_parts.append("注意：校园知识库中没有检索到相关信息。请基于你的通用知识尽量回答用户的问题。")
            prompt_parts.append("如果问题与校园无关或你无法回答，请礼貌告知。")
            prompt_parts.append("")
            prompt_parts.append("回答:")

        return "\n".join(prompt_parts)

    @classmethod
    def build_system_prompt(cls) -> str:
        """
        构建系统提示词
        
        Returns:
            系统提示词字符串
        """
        return cls.SYSTEM_PROMPT

    @classmethod
    def build_messages_for_llm(
        cls,
        question: str,
        contexts: List[dict],
        chat_history: Optional[List[dict]] = None,
        model_name: Optional[str] = None,
    ) -> List[dict]:
        """
        构建发送给 LLM 的消息列表
        
        Args:
            question: 用户问题
            contexts: 检索到的上下文信息
            chat_history: 对话历史
            model_name: 当前使用的模型名称（可选）
            
        Returns:
            消息列表，格式:
            [
                {"role": "system", "content": "系统提示词"},
                {"role": "user", "content": "完整提示词"},
            ]
        """
        messages = [
            {"role": "system", "content": cls.build_system_prompt()},
        ]

        user_content = cls.build_rag_prompt(question, contexts, chat_history, model_name)
        messages.append({"role": "user", "content": user_content})

        return messages
