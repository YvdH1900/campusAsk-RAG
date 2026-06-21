"""
文本分块服务（重构版 - 结构化优先）
====================================
分块优先级严格遵守：结构优先 > 长度保底，严禁纯按字符数硬切。

第一优先级：严格按文档标题层级、段落边界、列表条目边界切分
兜底：所有块设置最大长度上限，超过则强制按句子边界拆分

清洗流水线集成：
  1. 全文粗洗：解析后立即执行
  2. 父块精洗 + 校验：不合格的父块直接丢弃
  3. 子块轻校验：只做非空、最小长度校验
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

from app.services.document_cleaner import document_cleaner


# ==================== 章节标题模式 ====================

# 多级标题模式（按优先级排列）
# 注意：HEADING_PATTERNS 不应匹配条款标记，条款标记由 CLAUSE_PATTERNS 处理
# 否则会导致文本被条款标记（如 （一）（二） ）拆成极小父块，丢失大量内容
HEADING_PATTERNS = [
    # 一级标题：第X章、第X部分、第X篇、第X节
    re.compile(r'^第[一二三四五六七八九十百零\d]+[章篇部分节]\s*[：:、]?\s*.{0,50}$'),
    re.compile(r'^[一二三四五六七八九十]+[、.．]\s*.{2,50}$'),
    # 二级标题：带编号的节标题
    re.compile(r'^\d{1,2}[、.．]\s*.{2,50}$'),
    re.compile(r'^\d{1,2}\.\d{1,2}\s+.{2,50}$'),
    # 三级标题：数字编号、字母编号
    re.compile(r'^[（(]\d+[）)]\s*.{0,50}$'),
    re.compile(r'^[a-zA-Z][、.．]\s*.{2,50}$'),
    # Markdown 标题
    re.compile(r'^#{1,6}\s+.{2,}$'),
]

# 条款编号
CLAUSE_PATTERNS = [
    re.compile(r'^第[一二三四五六七八九十百零\d]+条\s*[：:、]?\s*'),
    re.compile(r'^第[一二三四五六七八九十百零\d]+条\s*$'),
    re.compile(r'^[（(][一二三四五六七八九十]+[）)]\s*'),
    re.compile(r'^[（(]\d+[）)]\s*'),
    re.compile(r'^\d{1,2}[、.．]\s*'),
    re.compile(r'^[a-zA-Z][、.．]\s*'),
]

# 列表条目
LIST_PATTERNS = [
    re.compile(r'^[-*•·]\s+'),
    re.compile(r'^\d+[.、．]\s+'),
    re.compile(r'^[（(]\d+[）)]\s+'),
]


def _is_heading(line: str) -> Tuple[bool, int]:
    """判断是否为标题，返回 (is_heading, level)"""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False, 0
    for level, pattern in enumerate(HEADING_PATTERNS):
        if pattern.match(stripped):
            return True, min(level + 1, 3)  # 1-3 级
    return False, 0


def _is_clause_start(line: str) -> bool:
    """判断是否为条款开头"""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in CLAUSE_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def _is_list_item(line: str) -> bool:
    """判断是否为列表条目"""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in LIST_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def _split_by_sentences(text: str) -> List[str]:
    """按句子边界拆分（用于兜底强制拆分）"""
    # 句子边界：。！？\n
    sentences = re.split(r'(?<=[。！？])\s*', text)
    result = []
    for s in sentences:
        s = s.strip()
        if s:
            # 如果还太长，再按逗号分
            if len(s) > 800:
                subs = re.split(r'(?<=[，；：])', s)
                for sub in subs:
                    sub = sub.strip()
                    if sub:
                        result.append(sub)
            else:
                result.append(s)
    return result


class TextSplitter:
    """
    结构化优先分块器

    分块流程：
    1. 全文粗洗（解析后立即执行）
    2. 按标题层级拆父块
    3. 父块精洗 + 校验（不合格丢弃）
    4. 父块内按条款/列表/段落拆子块
    5. 子块轻校验
    6. 子块超长 → 按句子边界兜底拆分
    """

    def __init__(
        self,
        parent_chunk_size: int = 1500,
        parent_chunk_overlap: int = 200,
        child_chunk_size: int = 500,
        child_chunk_overlap: int = 60,
        max_chunk_size: int = 800,  # 硬上限，超过则强制拆分
    ):
        self.parent_chunk_size = parent_chunk_size
        self.parent_chunk_overlap = parent_chunk_overlap
        self.child_chunk_size = child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap
        self.max_chunk_size = max_chunk_size

    def split(self, text: str, parent_id_prefix: str = "") -> List[Dict]:
        """
        执行完整的分块流水线

        Args:
            text: 经过粗洗的文本
            parent_id_prefix: 父块ID前缀，多文件拆分时用于防止parent_id碰撞
                              例如 "s0_", "s1_" 等

        Returns:
            [{"parent_id", "parent_content", "child_id", "child_content"}, ...]
        """
        if not text or not text.strip():
            return []

        # 1. 确保已粗洗（解析器 parse() 默认已执行粗洗，此处不再重复）

        # 2. 按标题层级拆父块
        parent_blocks = self._split_parents_by_headings(text)
        logger.info(f"父块拆分: {len(parent_blocks)} 个父块")

        # 3. 父块精洗 + 校验（校验不通过时保留原文，不丢弃）
        validated_parents = []
        for parent_text in parent_blocks:
            cleaned, quality = document_cleaner.fine_clean_parent(parent_text)
            if cleaned is not None:
                validated_parents.append(cleaned)
            else:
                # 精洗校验不通过时保留原始文本，避免大量内容丢失
                validated_parents.append(parent_text)
                logger.debug(f"父块校验未通过但保留原文: {quality.get('reason', 'unknown')}")

        if not validated_parents:
            logger.warning("所有父块在校验中被丢弃")
            return []

        # 4. 去重
        dup_indices = set(document_cleaner.detect_duplicates(validated_parents))
        validated_parents = [p for i, p in enumerate(validated_parents) if i not in dup_indices]
        if dup_indices:
            logger.info(f"父块去重: 移除 {len(dup_indices)} 个重复块")

        # 5. 每个父块内拆子块
        chunks = []
        for p_idx, parent_content in enumerate(validated_parents):
            parent_id = f"{parent_id_prefix}p{p_idx}"

            # 父块内按条款/列表/段落拆子块
            child_texts = self._split_children(parent_content)

            # 子块轻校验
            for c_idx, child_content in enumerate(child_texts):
                validated_child, child_quality = document_cleaner.light_validate_child(child_content)
                if validated_child is None:
                    continue

                child_id = f"{parent_id}_c{c_idx}"
                chunks.append({
                    "parent_id": parent_id,
                    "parent_content": parent_content,
                    "child_id": child_id,
                    "child_content": validated_child,
                })

        logger.info(f"子块拆分: {len(chunks)} 个子块（来自 {len(validated_parents)} 个父块）")

        return chunks

    def _split_parents_by_headings(self, text: str) -> List[str]:
        """按标题层级拆父块"""
        lines = text.split('\n')
        heading_positions = []

        for i, line in enumerate(lines):
            is_heading, level = _is_heading(line)
            if is_heading:
                heading_positions.append((i, level))

        if len(heading_positions) < 2:
            # 无标题结构，尝试按条款拆
            clauses = self._split_by_clauses(text)
            if len(clauses) >= 2:
                return self._group_clauses_into_parents(clauses)
            # 完全无结构，按段落拆分
            return self._split_by_paragraphs(text)

        # 按标题构建父块
        parents = []
        
        # 收集第一个标题之前的内容（标题、前言、介绍等）
        pre_heading_lines = lines[:heading_positions[0][0]]
        pre_heading_text = '\n'.join(pre_heading_lines).strip()
        # 保留所有非空前置内容（校训、简介等可能很短但很重要）
        clean_pre = pre_heading_text.strip()
        if clean_pre:
            # 如果前置内容过长，按段落分
            if len(clean_pre) > self.parent_chunk_size * 2:
                parents.extend(self._split_by_paragraphs(clean_pre))
            else:
                parents.append(clean_pre)
        
        for h_idx in range(len(heading_positions)):
            start_line = heading_positions[h_idx][0]
            if h_idx + 1 < len(heading_positions):
                end_line = heading_positions[h_idx + 1][0]
            else:
                end_line = len(lines)

            block_lines = lines[start_line:end_line]
            block_text = '\n'.join(block_lines).strip()

            if block_text:
                # 如果父块过大，在子标题处再拆分
                if len(block_text) > self.parent_chunk_size * 2:
                    sub_blocks = self._split_oversized_parent(block_text)
                    parents.extend(sub_blocks)
                else:
                    parents.append(block_text)

        # 合并连续的过小父块（如被误判为标题的连续列表条目）
        parents = self._merge_tiny_parents(parents)

        return parents

    def _split_oversized_parent(self, text: str) -> List[str]:
        """拆分过大的父块（在子标题处拆分）"""
        lines = text.split('\n')
        sub_heading_positions = []

        for i, line in enumerate(lines):
            is_heading, level = _is_heading(line)
            if is_heading and level >= 2:
                sub_heading_positions.append(i)

        if len(sub_heading_positions) < 2:
            # 无子标题，按段落拆分
            return self._split_by_paragraphs(text)

        blocks = []
        for h_idx in range(len(sub_heading_positions)):
            start = sub_heading_positions[h_idx]
            end = sub_heading_positions[h_idx + 1] if h_idx + 1 < len(sub_heading_positions) else len(lines)
            block = '\n'.join(lines[start:end]).strip()
            if block:
                blocks.append(block)

        return blocks

    def _merge_tiny_parents(self, parents: List[str]) -> List[str]:
        """合并连续的过小父块（如被误判为标题的连续列表条目）"""
        if len(parents) <= 1:
            return parents
        
        merged = []
        buffer = []
        buffer_size = 0
        
        for parent in parents:
            parent_len = len(parent)
            # 如果当前块很小（< 100字符），且缓冲区+当前块不会超过限制，则合并
            if parent_len < 100 and buffer_size + parent_len < self.parent_chunk_size:
                buffer.append(parent)
                buffer_size += parent_len
            else:
                # 先清空缓冲区
                if buffer:
                    merged.append('\n\n'.join(buffer))
                    buffer = []
                    buffer_size = 0
                # 当前块单独加入
                if parent_len < 100 and parent_len < self.parent_chunk_size:
                    buffer.append(parent)
                    buffer_size = parent_len
                else:
                    merged.append(parent)
        
        if buffer:
            merged.append('\n\n'.join(buffer))
        
        return merged

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """按段落拆分（无结构回退）"""
        paragraphs = re.split(r'\n\s*\n', text)
        blocks = []
        current_block = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_len = len(para)

            if current_size + para_len > self.parent_chunk_size and current_block:
                blocks.append('\n\n'.join(current_block))
                current_block = [para]
                current_size = para_len
            else:
                current_block.append(para)
                current_size += para_len

        if current_block:
            blocks.append('\n\n'.join(current_block))

        return blocks

    def _split_by_clauses(self, text: str) -> List[str]:
        """按条款拆分"""
        lines = text.split('\n')
        clauses = []
        current_clause_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_clause_lines:
                    current_clause_lines.append('')
                continue

            if _is_clause_start(stripped) and current_clause_lines:
                clause_text = '\n'.join(current_clause_lines).strip()
                if clause_text:
                    clauses.append(clause_text)
                current_clause_lines = [line]
            else:
                current_clause_lines.append(line)

        if current_clause_lines:
            clause_text = '\n'.join(current_clause_lines).strip()
            if clause_text:
                clauses.append(clause_text)

        return clauses

    def _group_clauses_into_parents(self, clauses: List[str]) -> List[str]:
        """将条款聚合为父块"""
        parents = []
        current_group = []
        current_size = 0

        for clause in clauses:
            clause_len = len(clause)
            if current_size + clause_len > self.parent_chunk_size and current_group:
                parents.append('\n\n'.join(current_group))
                current_group = [clause]
                current_size = clause_len
            else:
                current_group.append(clause)
                current_size += clause_len

        if current_group:
            parents.append('\n\n'.join(current_group))

        return parents

    def _split_children(self, parent_text: str) -> List[str]:
        """父块内拆子块（按条款/列表/段落/句子）"""
        if not parent_text or not parent_text.strip():
            return []

        # 1. 尝试按条款拆分
        clauses = self._split_by_clauses(parent_text)
        if len(clauses) >= 2:
            children = []
            for clause in clauses:
                if len(clause) > self.max_chunk_size:
                    children.extend(_split_by_sentences(clause))
                else:
                    children.append(clause)
            return children

        # 2. 尝试按列表条目拆分
        lines = parent_text.split('\n')
        children = []
        current_child = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_child:
                    current_child.append('')
                continue

            is_list = _is_list_item(stripped)
            is_heading, _ = _is_heading(stripped)

            # 遇到新列表条目 或 新标题 → 开始新子块
            if (is_list or is_heading) and current_child:
                child_text = '\n'.join(current_child).strip()
                if child_text:
                    children.append(child_text)
                current_child = [line]
            else:
                current_child.append(line)

        if current_child:
            child_text = '\n'.join(current_child).strip()
            if child_text:
                children.append(child_text)

        if len(children) >= 2:
            return children

        # 3. 按段落拆分
        paragraphs = re.split(r'\n\s*\n', parent_text)
        children = [p.strip() for p in paragraphs if p.strip()]

        if len(children) >= 2:
            return children

        # 4. 兜底：按句子边界 + 长度限制
        if len(parent_text) > self.max_chunk_size:
            return _split_by_sentences(parent_text)

        return [parent_text]

    # ==================== 质量评估 ====================

    def evaluate_quality(self, chunks: List[Dict]) -> Dict:
        """评估分块质量"""
        if not chunks:
            return {"quality": "empty", "details": {}}

        child_sizes = [len(chunk["child_content"]) for chunk in chunks]
        parent_ids = set(c["parent_id"] for c in chunks)
        parent_sizes = [len(chunk["parent_content"]) for chunk in chunks]

        avg_child_size = sum(child_sizes) / len(child_sizes) if child_sizes else 0
        avg_parent_size = sum(parent_sizes) / len(parent_ids) if parent_ids else 0

        too_short = sum(1 for s in child_sizes if s < 10)
        too_long = sum(1 for s in child_sizes if s > self.max_chunk_size)

        if too_short > len(child_sizes) * 0.3 or too_long > len(child_sizes) * 0.1:
            quality = "poor"
        elif too_short > len(child_sizes) * 0.1:
            quality = "fair"
        else:
            quality = "good"

        return {
            "quality": quality,
            "total_children": len(child_sizes),
            "total_parents": len(parent_ids),
            "avg_child_size": round(avg_child_size, 1),
            "avg_parent_size": round(avg_parent_size, 1),
            "too_short": too_short,
            "too_long": too_long,
        }

    def split_simple(self, text: str) -> List[str]:
        """简单分块（仅父块，用于向前兼容）"""
        chunks = self.split(text)
        parent_ids = []
        seen = set()
        for chunk in chunks:
            if chunk["parent_id"] not in seen:
                seen.add(chunk["parent_id"])
                parent_ids.append(chunk["parent_content"])
        return parent_ids