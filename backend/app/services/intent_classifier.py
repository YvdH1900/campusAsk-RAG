"""
意图识别服务
============
基于规则和关键词的轻量级意图分类器
支持：
- 事实型问题（时间、地点、人物等）
- 流程型问题（如何办理、步骤等）
- 政策型问题（规定、要求、条件等）
- 闲聊型（问候、感谢等）
- 根据意图动态调整检索策略
"""

import logging
import re
from typing import Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """意图类型"""
    FACT = "fact"  # 事实型
    PROCESS = "process"  # 流程型
    POLICY = "policy"  # 政策型
    CHAT = "chat"  # 闲聊型
    UNKNOWN = "unknown"  # 未知


class IntentConfig:
    """意图配置"""
    
    # 事实型问题关键词
    FACT_KEYWORDS = [
        "什么时候", "何时", "几点", "哪年", "哪月", "哪日", "几号",
        "在哪里", "哪儿", "哪个校区",
        "是谁", "哪个老师", "谁负责",
        "多少", "几门", "几个",
        "是什么", "什么意思", "定义",
        "电话", "联系方式", "地址",
    ]
    
    # 流程型问题关键词
    PROCESS_KEYWORDS = [
        "怎么", "如何", "怎样",
        "办理流程", "申请流程", "步骤",
        "怎么办", "怎么申请", "怎么办理",
        "需要什么材料", "准备什么",
        "第一步", "第二步", "流程",
        "去哪里办", "到哪里",
    ]
    
    # 政策型问题关键词
    POLICY_KEYWORDS = [
        "规定", "要求", "条件", "政策",
        "能不能", "可以吗", "允许",
        "限制", "必须", "需要",
        "资格", "资格线", "标准",
        "奖学金", "助学金", "资助",
        "休学", "退学", "转专业",
    ]
    
    # 闲聊型问题关键词
    CHAT_KEYWORDS = [
        "你好", "您好", "嗨", "hi", "hello",
        "谢谢", "感谢", "辛苦了",
        "再见", "拜拜",
        "你是谁", "你能做什么", "你叫什么",
        "哈哈", "呵呵",
    ]
    
    # 闲聊型正则表达式
    CHAT_PATTERNS = [
        r"^[你好嗨]*[，,]*[呀啊]*[！!]*$",
        r"^谢谢[你]*[了]*[！!]*$",
        r"^(你好|您好|嗨|hi|hello)[！!]*$",
    ]


class IntentClassifier:
    """意图分类器"""

    def __init__(self):
        """初始化意图分类器"""
        self.config = IntentConfig()

    def classify(self, question: str) -> Dict:
        """
        对用户问题进行意图分类
        
        Args:
            question: 用户问题
            
        Returns:
            {
                "intent": "fact/process/policy/chat/unknown",
                "confidence": 0.85,
                "strategy": {
                    "top_k": 5,
                    "use_expansion": True,
                    "require_high_confidence": False,
                }
            }
        """
        question_lower = question.lower().strip()
        
        # 1. 检查闲聊（最高优先级）
        if self._is_chat(question_lower):
            return {
                "intent": IntentType.CHAT,
                "confidence": 0.95,
                "strategy": {
                    "top_k": 0,  # 不检索
                    "use_expansion": False,
                    "require_high_confidence": False,
                    "direct_answer": True,
                }
            }
        
        # 2. 计算各类型得分
        scores = {
            IntentType.FACT: self._score_fact(question_lower),
            IntentType.PROCESS: self._score_process(question_lower),
            IntentType.POLICY: self._score_policy(question_lower),
        }
        
        # 3. 选择最高得分的类型
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        
        # 4. 如果得分太低，标记为未知
        if best_score < 0.3:
            best_intent = IntentType.UNKNOWN
            best_score = 0.5
        
        # 5. 根据意图生成策略
        strategy = self._get_strategy(best_intent)
        
        result = {
            "intent": best_intent,
            "confidence": round(best_score, 2),
            "strategy": strategy,
        }
        
        logger.info(f"意图识别: '{question[:30]}...' -> {best_intent} (置信度: {best_score:.2f})")
        return result

    def _is_chat(self, question: str) -> bool:
        """检查是否为闲聊"""
        # 关键词匹配
        for keyword in self.config.CHAT_KEYWORDS:
            if keyword in question:
                return True
        
        # 正则匹配
        for pattern in self.config.CHAT_PATTERNS:
            if re.match(pattern, question):
                return True
        
        return False

    def _score_fact(self, question: str) -> float:
        """计算事实型得分"""
        score = 0.0
        for keyword in self.config.FACT_KEYWORDS:
            if keyword in question:
                score += 0.3
        
        # 问题长度较短的更可能是事实型
        if len(question) < 15:
            score += 0.2
        
        return min(score, 1.0)

    def _score_process(self, question: str) -> float:
        """计算流程型得分"""
        score = 0.0
        for keyword in self.config.PROCESS_KEYWORDS:
            if keyword in question:
                score += 0.3
        
        # 包含"怎么"、"如何"的更可能是流程型
        if "怎么" in question or "如何" in question:
            score += 0.2
        
        return min(score, 1.0)

    def _score_policy(self, question: str) -> float:
        """计算政策型得分"""
        score = 0.0
        for keyword in self.config.POLICY_KEYWORDS:
            if keyword in question:
                score += 0.3
        
        # 包含疑问词的更可能是政策型
        if "能不能" in question or "可以吗" in question:
            score += 0.2
        
        return min(score, 1.0)

    def _get_strategy(self, intent: IntentType) -> Dict:
        """根据意图获取检索策略"""
        strategies = {
            IntentType.FACT: {
                "top_k": 3,  # 精确检索，少量结果
                "use_expansion": False,  # 不需要扩展
                "require_high_confidence": True,  # 要求高置信度
                "direct_answer": False,
            },
            IntentType.PROCESS: {
                "top_k": 8,  # 需要完整流程，多检索
                "use_expansion": True,  # 需要扩展
                "require_high_confidence": False,
                "direct_answer": False,
            },
            IntentType.POLICY: {
                "top_k": 5,  # 中等检索
                "use_expansion": True,  # 需要扩展
                "require_high_confidence": True,  # 政策要求准确
                "direct_answer": False,
            },
            IntentType.CHAT: {
                "top_k": 0,  # 不检索
                "use_expansion": False,
                "require_high_confidence": False,
                "direct_answer": True,
            },
            IntentType.UNKNOWN: {
                "top_k": 5,  # 默认策略
                "use_expansion": True,
                "require_high_confidence": False,
                "direct_answer": False,
            },
        }
        
        return strategies.get(intent, strategies[IntentType.UNKNOWN])


# 全局实例
intent_classifier = IntentClassifier()
