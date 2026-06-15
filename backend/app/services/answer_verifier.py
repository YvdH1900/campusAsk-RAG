"""
答案验证服务
============
验证 AI 生成答案的质量和准确性
支持两种模式：
1. AI 验证：使用 LLM 判断答案是否基于上下文（效果更好）
2. 规则验证：基于关键词匹配和覆盖率计算（fallback，零成本）
"""

import logging
import re
from typing import List, Dict, Optional
import jieba

logger = logging.getLogger(__name__)


class AnswerVerifier:
    """答案验证器"""

    def __init__(self):
        """初始化答案验证器"""
        self.min_context_coverage = 0.3  # 最低上下文覆盖率
        self.use_ai_verification = False  # 默认禁用，LLM 格式解析易误判

    def verify(
        self,
        answer: str,
        contexts: List[Dict],
        question: str,
        use_ai: Optional[bool] = None,
        model_name: str = "qwen-plus",
    ) -> Dict:
        """
        验证答案质量
        
        Args:
            answer: AI 生成的答案
            contexts: 检索到的上下文
            question: 原始问题
            use_ai: 是否使用 AI 验证（None 时使用实例默认值）
            model_name: AI 验证使用的 LLM 模型名称
            
        Returns:
            {
                "is_valid": True/False,
                "confidence": 0.85,
                "issues": ["问题列表"],
                "context_coverage": 0.75,
            }
        """
        issues = []
        
        # 1. 检查答案是否为空
        if not answer or not answer.strip():
            return {
                "is_valid": False,
                "confidence": 0.0,
                "issues": ["答案为空"],
                "context_coverage": 0.0,
            }

        # 2. 检查是否包含免责声明（表明 LLM 不确定）
        disclaimer_patterns = [
            r"我不确定",
            r"据说",
            r"据我所知",
            r"无法确认",
            r"我不清楚",
            r"不太确定",
            r"我无法",
        ]
        
        disclaimer_count = 0
        for pattern in disclaimer_patterns:
            if re.search(pattern, answer):
                disclaimer_count += 1
                issues.append(f"包含不确定表述: {pattern}")

        # 3. 计算上下文覆盖率
        context_coverage = self._calculate_context_coverage(answer, contexts)
        
        if context_coverage < self.min_context_coverage:
            issues.append(f"上下文覆盖率过低: {context_coverage:.2%}")

        # 4. 检查是否引用了来源（仅记录，不阻塞）
        has_citation = bool(re.search(r'\[来源[：:]', answer))

        # 5. 检查答案长度
        if len(answer) < 20:
            issues.append("答案过短")

        # 6. AI 验证（如果启用）
        ai_use_ai = use_ai if use_ai is not None else self.use_ai_verification
        ai_result = {}
        ai_reason = None
        if ai_use_ai:
            ai_result = self._ai_verify(answer, contexts, question, model_name)
            if ai_result.get("reason"):
                ai_reason = ai_result.get("reason")
            if ai_result.get("is_valid") is False:
                issues.append("AI 验证不通过")

        # 7. 计算总体置信度
        # AI 验证通过时，给予更高权重
        confidence = self._calculate_confidence(
            context_coverage=context_coverage,
            has_citation=has_citation,
            disclaimer_count=disclaimer_count,
            issues_count=len(issues),
            ai_confidence=ai_result.get("confidence", None),
        )

        # 企业级判断标准：多级置信度，而非二元判断
        # 只有置信度很低时才标记为无效
        if ai_use_ai and ai_result:
            # 有 AI 验证时，结合 AI 置信度和规则判断
            ai_confidence = ai_result.get("confidence", 0.5)
            # AI 置信度低于 0.4 且规则判断也不通过时，才标记为无效
            is_valid = not (ai_confidence < 0.4 and confidence < 0.4)
        else:
            # 无 AI 验证时，用规则判断（降低阈值避免过度拦截）
            is_valid = confidence >= 0.35

        logger.info(
            f"答案验证 (模型={model_name}): 置信度={confidence:.2f}, "
            f"上下文覆盖率={context_coverage:.2%}, "
            f"问题数={len(issues)}, "
            f"AI置信度={ai_result.get('confidence', 'N/A')}, "
            f"结果={'通过' if is_valid else '不通过'}"
        )

        return {
            "is_valid": is_valid,
            "confidence": round(confidence, 2),
            "issues": issues,
            "context_coverage": round(context_coverage, 2),
            "has_citation": has_citation,
            "ai_reason": ai_reason,
        }

    def _ai_verify(
        self,
        answer: str,
        contexts: List[Dict],
        question: str,
        model_name: str = "qwen-plus",
    ) -> Dict:
        """使用 LLM 进行答案验证"""
        try:
            context_text = "\n\n".join(
                f"[来源{i+1}] {ctx.get('content', '')}"
                for i, ctx in enumerate(contexts[:5])
            )
            
            prompt = (
                f"请判断以下答案是否准确基于提供的上下文信息。\n\n"
                f"问题：{question}\n\n"
                f"上下文：\n{context_text}\n\n"
                f"答案：{answer}\n\n"
                f"请严格按以下格式回答（每行一个答案，不要添加其他内容）：\n"
                f"第一行只写：是 或 否\n"
                f"第二行只写：有 或 无\n"
                f"第三行：简要说明理由（一句话）"
            )
            
            from dashscope import Generation
            response = Generation.call(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                result_format="message",
                temperature=0.1,
                max_tokens=200,
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content.strip()
                lines = [l.strip() for l in content.split("\n") if l.strip()]
                
                # 第一行：是否基于上下文
                is_based = None  # None 表示解析失败，使用默认值
                if lines:
                    first = lines[0].replace("：", "").replace(":", "").strip()
                    if first.startswith("是") or "基于" in first or "准确" in first or "合理" in first:
                        is_based = True
                    elif first.startswith("否") or "不基于" in first or "不准确" in first:
                        is_based = False
                
                # 第二行：是否有未提及的信息
                has_extra = None
                if len(lines) >= 2:
                    second = lines[1].replace("：", "").replace(":", "").strip()
                    if second.startswith("有") or "包含" in second or "超出" in second:
                        has_extra = True
                    elif second.startswith("无") or "未包含" in second or "没有" in second:
                        has_extra = False
                
                # 第三行：理由
                reason = ""
                if len(lines) >= 3:
                    reason = lines[2]
                else:
                    reason = content[:100]
                
                # 解析失败时，默认答案无效（系统准确性优先）
                if is_based is None:
                    logger.warning(f"AI 验证解析失败，内容: {content[:100]}")
                    is_based = False  # 默认无效，确保系统准确性
                    has_extra = True  # 默认可能有额外信息
                
                # 计算 AI 置信度：基于 is_based 和 has_extra 的组合
                if is_based and not has_extra:
                    confidence = 0.9
                elif is_based and has_extra:
                    confidence = 0.7  # 基于上下文但有额外信息
                elif not is_based and not has_extra:
                    confidence = 0.4  # 不基于上下文但没有额外信息
                else:
                    confidence = 0.2  # 不基于上下文且有额外信息
                
                return {
                    "is_valid": is_based,
                    "confidence": confidence,
                    "reason": reason,
                }
            
            logger.warning("AI 验证失败，使用规则验证结果")
        except Exception as e:
            logger.warning(f"AI 验证异常: {e}，使用规则验证结果")
        
        return {}

    def _calculate_context_coverage(
        self,
        answer: str,
        contexts: List[Dict],
    ) -> float:
        """
        计算答案与上下文的覆盖率
        
        Args:
            answer: AI 答案
            contexts: 检索上下文
            
        Returns:
            覆盖率 [0, 1]
        """
        if not contexts:
            return 0.0

        answer_lower = answer.lower()
        total_context = ""
        
        for ctx in contexts:
            total_context += ctx.get("content", "") + " "

        total_context_lower = total_context.lower()

        # 提取答案中的关键短语（使用 jieba 分词，支持中文）
        answer_phrases = set()
        words = list(jieba.cut(answer_lower))
        for i in range(len(words) - 2):
            phrase = "".join(words[i:i+3])
            if len(phrase) >= 4:  # 过滤太短的短语
                answer_phrases.add(phrase)

        if not answer_phrases:
            return 0.0

        # 计算有多少短语出现在上下文中
        matched_phrases = 0
        for phrase in answer_phrases:
            if phrase in total_context_lower:
                matched_phrases += 1

        coverage = matched_phrases / len(answer_phrases)
        return coverage

    def _calculate_confidence(
        self,
        context_coverage: float,
        has_citation: bool,
        disclaimer_count: int,
        issues_count: int,
        ai_confidence: Optional[float] = None,
    ) -> float:
        """
        计算答案置信度
        
        Args:
            context_coverage: 上下文覆盖率
            has_citation: 是否有引用
            disclaimer_count: 不确定表述数量
            issues_count: 问题数量
            ai_confidence: AI 验证置信度（可选）
            
        Returns:
            置信度 [0, 1]
        """
        confidence = 1.0

        # 上下文覆盖率权重 40%
        confidence *= (0.4 + 0.6 * context_coverage)

        # 引用加分 10%
        if has_citation:
            confidence += 0.1

        # 不确定表述减分
        confidence -= disclaimer_count * 0.1

        # 问题减分
        confidence -= issues_count * 0.05

        # AI 验证结果融合（如果可用）
        if ai_confidence is not None:
            confidence = 0.6 * confidence + 0.4 * ai_confidence

        return max(0.0, min(1.0, confidence))


# 全局实例
answer_verifier = AnswerVerifier()
