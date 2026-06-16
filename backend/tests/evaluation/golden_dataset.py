
"""
黄金评测数据集
==============
基于上海交通大学本科生学生手册(2025版)的标注问答对。
每个条目包含问题、预期关键词、预期内容片段和难度分类。

当用户上传PDF版文档后，retrieval_evaluator 会：
1. 用问题查询检索系统
2. 检查返回的chunks是否包含 expected_keywords/expected_content
3. 计算召回率、精确率、MRR等指标
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class GoldenQA:
    """单个黄金评测问答对"""
    question: str                                      # 问题文本
    expected_keywords: List[str] = field(default_factory=list)      # 预期检索结果中应出现的关键词
    expected_content: List[str] = field(default_factory=list)       # 预期检索结果中应包含的内容片段
    source_section: str = ""                           # 来源章节
    difficulty: str = "medium"                         # easy/medium/hard
    category: str = "retrieval"                        # retrieval / generation / both


# ============================================================
# Golden Dataset
# ============================================================
# 注: expected_keywords 和 expected_content 是"或"的关系——
#     检索结果命中任一即视为相关。
#     用 .lower() 做大小写不敏感匹配。
# ============================================================

GOLDEN_DATASET: List[GoldenQA] = [

    # ========= 校训与基本规定 =========
    GoldenQA(
        question="上海交通大学的校训是什么？",
        expected_keywords=["饮水思源", "爱国荣校"],
        expected_content=["饮水思源，爱国荣校"],
        source_section="第七条",
        difficulty="easy",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生在校期间享有哪些权利？",
        expected_keywords=["公正评价", "学历证书", "学位证书", "参与学校管理"],
        expected_content=["在思想品德、学业成绩、运动健康等方面获得科学、公正评价",
                          "完成学校规定学业后获得相应的学历证书、学位证书"],
        source_section="第八条",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生在校期间需要履行哪些义务？",
        expected_keywords=["恪守学术道德", "完成规定学业", "缴纳学费"],
        source_section="第九条",
        difficulty="medium",
        category="retrieval",
    ),

    # ========= 学籍管理 =========
    GoldenQA(
        question="上海交通大学新生如何进行入学注册？",
        expected_keywords=["录取通知书", "按期到校", "办理入学手续"],
        expected_content=["持录取通知书和学校规定的有关证件按期到校办理入学手续"],
        source_section="第十条",
        difficulty="easy",
        category="retrieval",
    ),
    GoldenQA(
        question="交大新生因病无法入学怎么办？",
        expected_keywords=["保留入学资格", "二级甲等以上医院", "疾病康复证明"],
        expected_content=["经学校指定的二级甲等以上医院明确诊断不宜在校学习但通过短期治疗可达到健康标准的，由本人申请"],
        source_section="第十二条",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生每学期如何注册？",
        expected_keywords=["注册日", "缴费", "暂缓缴费"],
        expected_content=["每学期开学时，学生应当按学校规定办理注册手续",
                          "未缴费学生不能注册"],
        source_section="第十四条",
        difficulty="easy",
        category="retrieval",
    ),
    GoldenQA(
        question="上海交通大学本科生可以转专业吗？需要什么条件？",
        expected_keywords=["转专业", "专家考核", "教务处审核"],
        expected_content=["符合学校转专业的有关要求，由申请转入学院组织专家考核并经教务处审核通过"],
        source_section="第二十五条",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="哪些情况下交大学生不能转专业？",
        expected_keywords=["不予转专业", "国家有相关规定", "录取前与学校有明确约定"],
        source_section="第二十六条",
        difficulty="medium",
        category="retrieval",
    ),

    # ========= 成绩与考核 =========
    GoldenQA(
        question="上海交通大学本科生课程成绩如何评定？考试作弊会怎样？",
        expected_keywords=["考试作弊", "该课程以零分计", "留校察看"],
        expected_content=["考试作弊或违反考核纪律的，该课程以零分计",
                          "对于严重违反考核纪律或者作弊的，视其违纪或者作弊情节，给予相应"],
        source_section="第二十二条",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生体育课成绩如何评定？",
        expected_keywords=["体育课为公共必修课", "游泳技能达标"],
        expected_content=["体育课为公共必修课",
                          "学生须熟练掌握一至两项运动技能，其中，游泳技能达标"],
        source_section="第十八条",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="创新创业活动可以算学分吗？",
        expected_keywords=["创新创业", "创新活动"],
        expected_content=["学生参加创新创业相关实践活动，",
                          "可以折算为实践学分"],
        source_section="第二十一条",
        difficulty="easy",
        category="retrieval",
    ),

    # ========= 休学与复学 =========
    GoldenQA(
        question="交大学生如何申请休学？休学后学费怎么退？",
        expected_keywords=["休学", "退还", "学费", "考试周和夏季学期不受理"],
        expected_content=["学生休学只能在春、秋季学期正常教学周内申请",
                          "考试周和夏季学期不受理休学申请",
                          "休学学生办理休学手续后该学年所交学费、住宿费经教务处等部门核准后，参照以下标准予以退还"],
        source_section="第三十一条、第三十五条",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生应征入伍可以保留学籍吗？",
        expected_keywords=["应征参加中国人民解放军", "保留其学籍至退役后2年",
                           "不计入最长学习年限"],
        expected_content=["在校学生应征参加中国人民解放军(含中国人民武装警察部队)，学校保留其学籍至退役后2年"],
        source_section="第三十八条",
        difficulty="easy",
        category="retrieval",
    ),

    # ========= 退学警告与试读 =========
    GoldenQA(
        question="交大学生的退学警告和试读制度是怎样的？",
        expected_keywords=["退学警告", "平均积点", "低于或等于1.7", "试读"],
        expected_content=["对于在校期间，累计平均积点(GPA)第二次低于或等于1.7的学生，予以第二次退学警告",
                          "试读由学生本人提出申请，并与学院担保人"],
        source_section="第四十一条、第四十二条",
        difficulty="hard",
        category="retrieval",
    ),
    GoldenQA(
        question="什么情况下交大学生会被退学？",
        expected_keywords=["应予退学", "休学期满", "连续两周未参加",
                           "超过学校规定期限未注册"],
        source_section="第四十三条",
        difficulty="hard",
        category="retrieval",
    ),

    # ========= 毕业与学位 =========
    GoldenQA(
        question="上海交通大学本科生的最长学习年限是多久？提前毕业需要什么手续？",
        expected_keywords=["最长学习年限", "规定学制", "提前", "学院审核", "教务处审批"],
        expected_content=["学生最长学习年限（含休学）一般不得超过规定学制二年",
                          "提前完成所在专业本科培养计划规定的教学内容",
                          "应当提前一个学期向所在学院申请，经所在学院审核、教务处审批"],
        source_section="第五十条",
        difficulty="hard",
        category="retrieval",
    ),
    GoldenQA(
        question="结业和肄业有什么区别？结业后还能换毕业证吗？",
        expected_keywords=["结业", "肄业", "返校重修", "换发毕业证书"],
        expected_content=["学生在最长学习年限内修读了所在专业本科培养计划规定的教学内容，但个别课程",
                          "因各种原因，在最长学习年限内仍有部分所在专业本科培养计划规定的教学内容尚未修读，做肄业处理",
                          "对于结业学生，学校允许其在最长学习年限内申请返校重修"],
        source_section="第五十二条、第五十四条",
        difficulty="hard",
        category="retrieval",
    ),

    # ========= 学分与课程 =========
    GoldenQA(
        question="交大学生课程免修需要什么条件？",
        expected_keywords=["平均积点在3.0以上", "免修考试", "第16", "17周"],
        expected_content=["免修：平均积点在3.0以上的学生通过自学或其他途径已掌握了某门课程",
                          "教务处教学运行管理办公室每学期第16、17周受理免修申请"],
        source_section="学分制课程修读管理规定",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生考试可以申请缓考吗？",
        expected_keywords=["缓考", "教学信息服务网", "提交缓考申请", "可由家长代为申请"],
        expected_content=["学生本人应于考前在教学信息服务网（网址：i.sjtu.edu.cn）提交缓考申请",
                          "因病不能申请的，可由家长代为申请"],
        source_section="缓考管理办法",
        difficulty="medium",
        category="retrieval",
    ),

    # ========= 课堂纪律 =========
    GoldenQA(
        question="上交大学生考试有哪些纪律要求？",
        expected_keywords=["有效身份证件", "15分钟", "通讯"],
        expected_content=["须持带有本人清晰头像的校园卡或身份证原件等有效身份证件",
                          "考试开始后15分钟仍未进入考场，视为自动放弃该课程考试",
                          "禁止使用具有存储、编程、查询、通讯等功能的电子设备"],
        source_section="学生考试纪律规定",
        difficulty="easy",
        category="retrieval",
    ),
    GoldenQA(
        question="考试作弊的处分等级有哪些？",
        expected_keywords=["警告", "严重警告", "记过", "留校察看", "开除学籍"],
        expected_content=["处分分为下列五种：（1）警告；（2）严重警告；（3）记过；（4）留校察看；（5）开除学籍"],
        source_section="第七十三条",
        difficulty="easy",
        category="retrieval",
    ),

    # ========= 奖学金与资助 =========
    GoldenQA(
        question="交大的奖学金评选原则是什么？",
        expected_keywords=["公平", "公正", "公开"],
        expected_content=["各类奖学金的评选必须体现公平、公正、公开的原则",
                          "奖学金评选工作在公开、公正、公平的原则下"],
        source_section="第七十二条",
        difficulty="medium",
        category="retrieval",
    ),

    # ========= 出国交流 =========
    GoldenQA(
        question="交大公派本科生出国交流有哪些要求？",
        expected_keywords=["公派", "担保人", "责任告知书", "返校"],
        expected_content=["学生本人以及担保人（学生的父母）签署的《上海交通大学本科生海外交流项目责任告知书》"],
        source_section="公派本科生出国(境)学习交流办法",
        difficulty="hard",
        category="retrieval",
    ),
    GoldenQA(
        question="自费出国留学期间学籍如何处理？",
        expected_keywords=["自费出国", "休学至多一次", "期限为一学年"],
        expected_content=["自费出国（境）学习休学期满，应于新学期开学两周内向学校申请复学",
                          "学生本科期间自费出国（境）学习申请休学至多一次，期限为一学年"],
        source_section="本科生自费出国(境)学习学籍管理规定",
        difficulty="hard",
        category="retrieval",
    ),

    # ========= 校园生活 =========
    GoldenQA(
        question="交大学生校园卡丢失了怎么办？",
        expected_keywords=["校园卡运行管理中心", "挂失", "补办"],
        expected_content=["学生如遗失学生证（校园卡），应立即挂失，确认丢失后，可到校园卡运行管理中心补办"],
        source_section="学生证、校徽管理办法",
        difficulty="easy",
        category="retrieval",
    ),
    GoldenQA(
        question="交大学生如何借用教室？",
        expected_keywords=["交我办", "临时借用", "教室申请", "复原", "赔偿"],
        expected_content=["借用人登录交我办的教室申请借用或crr.sjtu.edu.cn，依流程借用",
                          "如不复原或损坏教室设施设备，借用人承担相应的赔偿费用"],
        source_section="公共教学楼管理办法",
        difficulty="medium",
        category="retrieval",
    ),
    GoldenQA(
        question="校园内可以举行宗教传教活动吗？",
        expected_keywords=["不得在学校进行宗教活动", "教育与宗教相分离"],
        expected_content=["任何组织和个人不得在学校进行宗教活动"],
        source_section="第六十四条",
        difficulty="easy",
        category="retrieval",
    ),

    # ========= 双学位与辅修 =========
    GoldenQA(
        question="辅修专业的学分要求是多少？辅修证书怎么拿？",
        expected_keywords=["不少于18学分", "跨专业类", "先选先得"],
        expected_content=["辅修专业课程体系聚焦专业核心课程，总学分原则上不少于18学分",
                          "学生可在第3学期进行辅修专业报名"],
        source_section="本科生辅修专业修读管理办法",
        difficulty="hard",
        category="retrieval",
    ),
    GoldenQA(
        question="双学士学位的毕业证书和学位证书如何标注？",
        expected_keywords=["毕业证书上注明", "一本学士学位证书", "两个学士学位信息"],
        expected_content=["毕业证书上注明相关主修专业信息",
                          "双学士学位只发放一本学士学位证书，学士学位证书上注明所授予的两个学士学位信息"],
        source_section="双学士学位复合型人才培养项目实施管理办法",
        difficulty="hard",
        category="retrieval",
    ),
]


def get_questions_by_difficulty(difficulty: str) -> list:
    """按难度过滤"""
    return [qa for qa in GOLDEN_DATASET if qa.difficulty == difficulty]


def get_questions_by_category(category: str) -> list:
    """按类别过滤"""
    return [qa for qa in GOLDEN_DATASET if qa.category == category]


def get_dataset_stats() -> dict:
    """返回数据集统计信息"""
    return {
        "total": len(GOLDEN_DATASET),
        "by_difficulty": {
            d: len(get_questions_by_difficulty(d))
            for d in ["easy", "medium", "hard"]
        },
        "by_category": {
            c: len(get_questions_by_category(c))
            for c in set(qa.category for qa in GOLDEN_DATASET)
        },
    }


# ============================================================
# Golden Dataset 与文档一致性验证
# ============================================================

def _load_student_handbook() -> str:
    """
    加载学生手册 TXT 文件内容。
    从项目根目录查找 2025学生手册_修复版.txt。
    """
    import os
    # 相对于此文件的路径: tests/evaluation/golden_dataset.py -> 根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 可能的路径: 项目根目录 (backend/../../) 或 直接 backend 同级
    candidates = [
        os.path.join(current_dir, "..", "..", "..", "2025学生手册_修复版.txt"),
        os.path.join(current_dir, "..", "..", "2025学生手册_修复版.txt"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.exists(norm):
            with open(norm, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def validate_against_document(verbose: bool = False) -> dict:
    """
    验证 Golden Dataset 中所有 QA 对的关键词/内容是否确实出现在学生手册文档中。
    
    Args:
        verbose: 是否打印详细信息
        
    Returns:
        {
            "total_qa": int,
            "total_keywords": int,
            "total_content": int,
            "keyword_hit_rate": float,   # 关键词在文档中的命中率
            "content_hit_rate": float,   # 内容片段在文档中的命中率
            "issues": [dict, ...],       # 有问题的 QA 对
        }
    """
    doc_text = _load_student_handbook()
    if not doc_text:
        return {"error": "未找到学生手册文档", "total_qa": len(GOLDEN_DATASET)}
    
    # 标准化空白字符：去除所有空白（含换行），用于内容匹配
    import re
    doc_normalized = re.sub(r'\s+', '', doc_text)
    doc_lower = doc_normalized.lower()
    
    total_keywords = 0
    total_content = 0
    keyword_hits = 0
    content_hits = 0
    issues = []
    
    for i, qa in enumerate(GOLDEN_DATASET):
        missing_keywords = []
        missing_content = []
        
        for kw in qa.expected_keywords:
            total_keywords += 1
            # 关键词也做空白标准化
            kw_normalized = re.sub(r'\s+', '', kw).lower()
            if kw_normalized in doc_lower:
                keyword_hits += 1
            else:
                missing_keywords.append(kw)
        
        for ec in qa.expected_content:
            total_content += 1
            # 内容片段也做空白标准化
            ec_normalized = re.sub(r'\s+', '', ec).lower()
            if ec_normalized in doc_lower:
                content_hits += 1
            else:
                missing_content.append(ec[:60])
        
        if missing_keywords or missing_content:
            issues.append({
                "index": i + 1,
                "question": qa.question[:50],
                "difficulty": qa.difficulty,
                "missing_keywords": missing_keywords,
                "missing_content": missing_content,
            })
    
    keyword_rate = keyword_hits / max(total_keywords, 1)
    content_rate = content_hits / max(total_content, 1)
    
    if verbose:
        print(f"\nGolden Dataset 与文档一致性验证:")
        print(f"  关键词命中率: {keyword_rate:.1%} ({keyword_hits}/{total_keywords})")
        print(f"  内容命中率:   {content_rate:.1%} ({content_hits}/{total_content})")
        if issues:
            print(f"\n  存在问题的 QA 对 ({len(issues)}):")
            for issue in issues:
                print(f"    #{issue['index']} [{issue['difficulty']}] {issue['question']}")
                if issue["missing_keywords"]:
                    print(f"      缺少关键词: {issue['missing_keywords']}")
                if issue["missing_content"]:
                    print(f"      缺少内容: {issue['missing_content'][:1]}...")
    
    return {
        "total_qa": len(GOLDEN_DATASET),
        "total_keywords": total_keywords,
        "total_content": total_content,
        "keyword_hit_rate": keyword_rate,
        "content_hit_rate": content_rate,
        "issues": issues,
    }
