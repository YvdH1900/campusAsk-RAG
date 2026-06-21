"""
文档清洗服务（三级清洗流水线）
==============================
1. 全文粗洗：基础格式规范化 + 通用冗余移除
2. 父块精洗 + 校验：专项场景清洗 + 质量校验
3. 子块轻校验：非空 + 最小长度校验

清洗目标：
- 特殊空白字符、冗余空白、装饰性符号
- 页码、页眉页脚、模板化文案
- 非正文整页、异常断行、汉字间空格
- 识别错误碎片、识别噪音、修订痕迹
- 目录冗余、浮动元素、格式残留
- 低质量/空白/高度重复内容拦截
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


# ==================== 正则模式库 ====================

# 特殊空白字符
SPECIAL_WHITESPACE = re.compile(r'[\u3000\ufeff\u00a0\u2000-\u200f\u2028-\u202f\u205f\u2060\u00ad\u200b\u200c\u200d\u2061-\u2064\u2066-\u206f]')

# 控制字符（保留换行和制表符）
CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

# 冗余空白
MULTI_SPACES = re.compile(r' {2,}')
MULTI_NEWLINES = re.compile(r'\n{4,}')
LEADING_TRAILING_SPACES = re.compile(r'^[ \t]+|[ \t]+$', re.MULTILINE)

# 装饰性分隔线
DECORATIVE_LINE = re.compile(r'^[*-=~#]{3,}$')
PURE_SYMBOL_LINE = re.compile(r'^[^\w\u4e00-\u9fff]{3,}$')

# 页码格式
PAGE_NUMBER_PATTERNS = [
    re.compile(r'^第\s*[0-9零一二三四五六七八九十百千]+\s*页\s*[／/]?\s*[共总]?\s*[0-9零一二三四五六七八九十百千]+\s*页?$'),
    re.compile(r'^Page\s+\d+\s+of\s+\d+$', re.IGNORECASE),
    re.compile(r'^[-—]\s*\d+\s*[-—]$'),
    re.compile(r'^\d+\s*/\s*\d+$'),
    re.compile(r'^\d{1,4}$'),
    re.compile(r'^[（(]\s*\d+\s*[）)]$'),
]

# 页眉页脚常见关键词
HEADER_FOOTER_KEYWORDS = [
    '机密', '内部资料', '版权所有', '未经许可', '不得复制',
    'confidential', 'internal', 'copyright', 'all rights reserved',
    '文档编号', '版本号', '修订日期', '生效日期',
]

# 模板化文案（版权声明等）
TEMPLATE_PATTERNS = [
    re.compile(r'版权所有[©]?\s*[（(]?\d{4}[）)]?.*保留'),
    re.compile(r'最终解释权归.*所有'),
    re.compile(r'本[文档资料].*仅供参考'),
    re.compile(r'免责声明[：:].*'),
    re.compile(r'未经.*书面许可.*不得'),
    re.compile(r'Copyright\s*[©]?\s*\d{4}', re.IGNORECASE),
    re.compile(r'All\s+rights?\s+reserved', re.IGNORECASE),
    re.compile(r'Confidential.*Do\s+not\s+distribute', re.IGNORECASE),
]

# 目录特征
TOC_PATTERNS = [
    re.compile(r'^[.·•]{5,}$'),  # 引导点线
    re.compile(r'^[.·•\s]{3,}\d+$'),  # 点线+页码
    re.compile(r'^目\s*录\s*$'),
    re.compile(r'^Table\s+of\s+Contents$', re.IGNORECASE),
    re.compile(r'^CONTENTS$'),
]

# 异常断行：中文字符后的异常换行（非段落边界）
ABNORMAL_BREAK = re.compile(r'([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])\n([\u4e00-\u9fff])')

# 汉字间多余空格（仅匹配空格和制表符，不匹配换行符）
CHINESE_SPACE = re.compile(r'([\u4e00-\u9fff])[ \t]+([\u4e00-\u9fff])')

# 乱码/识别错误
GARBLED_BLOCK = re.compile(r'[\ufffd\ufffe\uffff\u25a1]{2,}')
GARBLED_SYMBOLS = re.compile(r'[^\w\u4e00-\u9fff\s.,;:!?()（）、。，；：！？""''""【】《》\n\-]{5,}')

# 修订痕迹
REVISION_MARKS = re.compile(r'<del>.*?</del>|\[删除\].*?\[/删除\]|【批注】.*?【/批注】', re.IGNORECASE)
STRIKETHROUGH = re.compile(r'[\u0336\u0335\u0337\u0338].*?[\u0336\u0335\u0337\u0338]')

# 格式残留
HIDDEN_FORMAT = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


class DocumentCleaner:
    """文档清洗器 - 三级流水线"""

    def __init__(
        self,
        min_effective_chars_per_page: int = 10,
        min_effective_chars_per_chunk: int = 2,
        min_effective_ratio: float = 0.30,
        max_duplicate_ratio: float = 0.92,
    ):
        self.min_effective_chars_per_page = min_effective_chars_per_page
        self.min_effective_chars_per_chunk = min_effective_chars_per_chunk
        self.min_effective_ratio = min_effective_ratio
        self.max_duplicate_ratio = max_duplicate_ratio

    # ==================== 一级：全文粗洗 ====================

    def coarse_clean(self, text: str) -> str:
        """
        全文粗洗：基础格式规范化 + 通用冗余移除
        
        在解析出原始文本后立即执行，得到规整的全文本。
        """
        if not text or not text.strip():
            return ""

        # 1. 移除特殊空白字符（全角空格、不间断空格、零宽字符等）
        text = SPECIAL_WHITESPACE.sub(' ', text)

        # 2. 移除控制字符（保留换行符）
        text = CONTROL_CHARS.sub('', text)

        # 3. 合并连续空格
        text = MULTI_SPACES.sub(' ', text)

        # 4. 移除行首行尾多余空格
        text = LEADING_TRAILING_SPACES.sub('', text)

        # 5. 合并3行以上连续空行 → 最多保留2个空行
        text = MULTI_NEWLINES.sub('\n\n\n', text)

        # 6. 移除纯装饰分隔线
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append('')
                continue
            if DECORATIVE_LINE.match(stripped):
                continue
            if PURE_SYMBOL_LINE.match(stripped) and len(stripped) < 80:
                continue
            cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

        # 7. 移除页码行
        text = self._remove_page_numbers(text)

        # 8. 移除模板化版权声明
        for pattern in TEMPLATE_PATTERNS:
            text = pattern.sub('', text)

        # 9. 修复异常断行（中文句子中间被拆分的换行）
        text = ABNORMAL_BREAK.sub(r'\1\2', text)

        # 10. 移除汉字间多余空格
        text = CHINESE_SPACE.sub(r'\1\2', text)

        # 11. 移除修订痕迹
        text = REVISION_MARKS.sub('', text)
        text = STRIKETHROUGH.sub('', text)

        # 12. 移除隐藏格式标记
        text = HIDDEN_FORMAT.sub('', text)

        # 13. 最终合并空行
        text = MULTI_NEWLINES.sub('\n\n', text)

        return text.strip()

    def _remove_page_numbers(self, text: str) -> str:
        """移除页码"""
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                cleaned.append('')
                continue
            is_page_num = False
            for pattern in PAGE_NUMBER_PATTERNS:
                if pattern.match(stripped):
                    is_page_num = True
                    break
            if not is_page_num:
                cleaned.append(line)
        return '\n'.join(cleaned)

    # ==================== 二级：父块精洗（轻量） ====================

    def fine_clean_parent(self, parent_text: str) -> Tuple[Optional[str], Dict]:
        """
        父块轻量清洗

        粗洗已在解析阶段完成，这里只做最基本的空白整理。
        不再做质量校验丢弃，避免丢失有效内容。

        Returns:
            (cleaned_text, quality_report)
        """
        if not parent_text or not parent_text.strip():
            return None, {"reason": "empty", "quality": "rejected"}

        text = parent_text.strip()

        # 仅做基本空白整理
        text = MULTI_NEWLINES.sub('\n\n', text)
        text = MULTI_SPACES.sub(' ', text)
        text = text.strip()

        return text, {"quality": "accepted", "total_chars": len(text)}

    # ==================== 三级：子块轻校验（仅非空） ====================

    def light_validate_child(self, child_text: str) -> Tuple[Optional[str], Dict]:
        """
        子块非空校验

        只做非空检查，不做长度限制，避免丢失有效内容。

        Returns:
            (text_or_None, validation_report)
        """
        if not child_text or not child_text.strip():
            return None, {"reason": "empty", "valid": False}

        text = child_text.strip()
        return text, {"valid": True, "length": len(text)}

    # ==================== 重复检测 ====================

    @staticmethod
    def detect_duplicates(texts: List[str], threshold: float = 0.95) -> List[int]:
        """
        检测高度重复内容索引
        
        Args:
            texts: 文本列表
            threshold: 相似度阈值（默认 0.95，仅移除几乎完全相同的内容）
        
        Returns:
            需要移除的重复文本索引列表
        """
        if len(texts) <= 1:
            return []

        # 使用简化的 Jaccard 相似度
        def tokenize(t: str) -> set:
            return set(t[i:i+3] for i in range(0, len(t)-2))

        duplicates = set()
        for i in range(len(texts)):
            if i in duplicates:
                continue
            tokens_i = tokenize(texts[i])
            if not tokens_i:
                continue
            for j in range(i + 1, len(texts)):
                if j in duplicates:
                    continue
                tokens_j = tokenize(texts[j])
                if not tokens_j:
                    continue
                intersection = len(tokens_i & tokens_j)
                union = len(tokens_i | tokens_j)
                if union > 0 and intersection / union >= threshold:
                    duplicates.add(j)

        return sorted(duplicates)

    # ==================== 全流水线 ====================

    def full_pipeline(self, raw_text: str) -> Tuple[Optional[str], Dict]:
        """
        完整清洗流水线
        
        Args:
            raw_text: 原始解析文本
        
        Returns:
            (cleaned_text, pipeline_report)
        """
        report = {
            "coarse_clean": {"status": "skipped"},
            "fine_clean": {"status": "skipped"},
            "duplicate_check": {"status": "skipped"},
        }

        if not raw_text or not raw_text.strip():
            report["coarse_clean"] = {"status": "empty"}
            return None, report

        # 一级：粗洗
        text = self.coarse_clean(raw_text)
        report["coarse_clean"] = {"status": "completed", "length": len(text)}

        if not text or len(text) < self.min_effective_chars_per_page:
            report["coarse_clean"]["status"] = "rejected_too_short"
            return None, report

        # 二级：精洗 + 校验
        text, quality = self.fine_clean_parent(text)
        report["fine_clean"] = quality

        if text is None:
            return None, report

        return text, report


# 全局单例
document_cleaner = DocumentCleaner()