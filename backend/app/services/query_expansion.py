"""
查询扩展服务
============
对用户问题进行同义词扩展，提高检索召回率
支持两种模式：
1. AI 扩展：使用 LLM 生成语义相似的变体问题（效果更好）
2. 规则扩展：基于内置同义词表扩展（fallback，零成本）
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class QueryExpansionService:
    """查询扩展服务"""

    SYNONYM_MAP = {
        "入学": ["报到", "注册", "新生", "录取", "入学手续"],
        "毕业": ["学位", "论文", "答辩", "离校"],
        "考试": ["考核", "测试", "测验", "笔试", "面试"],
        "奖学金": ["助学金", "资助", "补助", "奖金"],
        "宿舍": ["寝室", "住宿", "公寓", "床位"],
        "选课": ["课程", "学分", "必修", "选修"],
        "请假": ["休假", "病假", "事假", "请假条"],
        "学籍": ["档案", "注册", "休学", "退学"],
        "实习": ["实践", "实训", "校企合作", "就业"],
        "图书馆": ["借阅", "还书", "图书", "阅览室"],
        "食堂": ["餐厅", "就餐", "伙食", "用餐"],
        "军训": ["军事训练", "国防教育", "体能训练"],
        "学费": ["缴费", "收费", "住宿费", "杂费", "缴纳"],
        "义务": ["责任", "遵守", "履行", "缴纳", "规定"],
        "办理": ["申请", "办", "处理", "办理手续"],
        "手续": ["流程", "程序", "步骤", "环节"],
        "注册": ["入学", "报到", "办理", "登记", "录取"],
        "转专业": ["专业调整", "专业变更", "跨专业"],
        "四六级": ["英语等级考试", "CET", "英语四级", "英语六级"],
        "考研": ["研究生考试", "硕士", "博士", "研究生"],
        "辅导员": ["班主任", "导师", "指导教师"],
        "学生会": ["社团", "团委", "学生组织"],
        "校医院": ["医务室", "看病", "就医", "体检"],
        "校园卡": ["一卡通", "饭卡", "学生卡"],
    }

    @classmethod
    def expand(cls, query: str, max_expansions: int = 3) -> List[str]:
        """
        扩展查询问题（规则模式）
        
        Args:
            query: 原始问题
            max_expansions: 最大扩展词数量
            
        Returns:
            扩展后的查询词列表
        """
        expanded = [query]
        
        for keyword, synonyms in cls.SYNONYM_MAP.items():
            if keyword in query:
                for synonym in synonyms[:max_expansions]:
                    if synonym not in query:
                        expanded.append(synonym)
        
        if len(expanded) > 1:
            logger.info(f"规则查询扩展: '{query}' -> {expanded}")
        
        return expanded

    @classmethod
    def expand_query_for_retrieval(cls, query: str, use_ai: bool = False, model_name: Optional[str] = None) -> str:
        """
        生成用于检索的扩展查询字符串
        
        Args:
            query: 原始问题
            use_ai: 是否使用 AI 扩展
            model_name: AI 模型名称（use_ai=True 时使用）
            
        Returns:
            扩展后的查询字符串
        """
        if use_ai and model_name:
            try:
                expanded = cls.ai_expand_with_model(query, model_name)
                result = " ".join(expanded)
                logger.info(f"AI 查询扩展: '{query}' -> '{result}'")
                return result
            except Exception as e:
                logger.warning(f"AI 查询扩展失败: {e}，降级到规则扩展")
        
        expanded = cls.expand(query)
        return " ".join(expanded)

    @classmethod
    def ai_expand_with_model(cls, query: str, model_name: str, max_expansions: int = 3) -> List[str]:
        """
        使用指定模型进行 AI 查询扩展
        
        Args:
            query: 原始问题
            model_name: AI 模型名称
            max_expansions: 最大扩展数量
            
        Returns:
            扩展后的查询词列表
        """
        try:
            prompt = (
                f"请为以下校园相关问题生成 {max_expansions} 个语义相似的关键词或短语，"
                f"用于提高搜索引擎的召回率。每个词用换行分隔，只输出词本身，不要编号或解释：\n\n"
                f"原问题：{query}"
            )
            
            from dashscope import Generation
            response = Generation.call(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                result_format="message",
                temperature=0.7,
                max_tokens=200,
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content.strip()
                expansions = [line.strip() for line in content.split("\n") if line.strip()]
                expansions = expansions[:max_expansions]
                
                if expansions:
                    return [query] + expansions
            
            raise RuntimeError(f"AI 查询扩展返回空或失败: status={response.status_code}")
        except Exception as e:
            raise RuntimeError(f"AI 查询扩展异常: {e}")
