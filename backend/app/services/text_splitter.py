"""
文本分块服务（规则驱动父子分块）
==============================
按文档结构语义分块，而非固定字数切割：
1. 父块：按章节/一级标题拆分，保留完整上下文
2. 子块：按条款编号（第X条、1.XXX）拆分，一条规则一个子块

适用于校规/制度/手册类结构化文档，大小文档通用。
"""

import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


# 条款编号正则（按优先级排列）
CLAUSE_PATTERNS = [
    re.compile(r'^第[一二三四五六七八九十百零\d]+条\s*[：:、]?\s*'),
    re.compile(r'^第[一二三四五六七八九十百零\d]+条\s*$'),
    re.compile(r'^[（(][一二三四五六七八九十]+[）)]\s*'),
    re.compile(r'^[（(]\d+[）)]\s*'),
    re.compile(r'^\d{1,2}[、.．]\s*'),
    re.compile(r'^[a-zA-Z][、.．]\s*'),
]

# 章节标题正则（用于父块切分）
SECTION_PATTERNS = [
    re.compile(r'^第[一二三四五六七八九十百零\d]+[章篇部分]\s+'),
    re.compile(r'^[一二三四五六七八九十]+[、.．]\s+'),
    re.compile(r'^[（(][一二三四五六七八九十]+[）)]\s+'),
    re.compile(r'^\d{1,2}[、.．]\s+\S{2,}'),
]


def _is_section_header(line: str) -> bool:
    """判断一行是否为章节/一级标题"""
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    for pattern in SECTION_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def _is_clause_start(line: str) -> bool:
    """判断一行是否为条款开头"""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in CLAUSE_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def _split_by_clauses(text: str) -> List[str]:
    """
    按条款编号将文本拆分为独立条款列表。
    每个条款以 "第X条"、"1."、"(一)" 等开头。
    """
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
            # 遇到新条款，保存之前的
            clause_text = '\n'.join(current_clause_lines).strip()
            if clause_text:
                clauses.append(clause_text)
            current_clause_lines = [line]
        else:
            current_clause_lines.append(line)

    # 保存最后一个条款
    if current_clause_lines:
        clause_text = '\n'.join(current_clause_lines).strip()
        if clause_text:
            clauses.append(clause_text)

    return clauses


def _split_by_sections(text: str) -> List[str]:
    """
    按章节标题将文本拆分为独立章节列表。
    每个章节以 "第一章"、"一、" 等标题开头。
    """
    lines = text.split('\n')
    sections = []
    current_section_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section_lines:
                current_section_lines.append('')
            continue

        if _is_section_header(stripped) and current_section_lines:
            section_text = '\n'.join(current_section_lines).strip()
            if section_text:
                sections.append(section_text)
            current_section_lines = [line]
        else:
            current_section_lines.append(line)

    if current_section_lines:
        section_text = '\n'.join(current_section_lines).strip()
        if section_text:
            sections.append(section_text)

    return sections


def _fallback_split(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    回退方案：对无结构文本按段落/句子切分。
    用于不含条款编号的普通文本（如前言、附录）。
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if c.strip()]


class TextSplitter:
    """规则驱动父子分块器"""

    def __init__(
        self,
        parent_chunk_size: int = 1500,
        parent_chunk_overlap: int = 200,
        child_chunk_size: int = 500,
        child_chunk_overlap: int = 60,
    ):
        """
        Args:
            parent_chunk_size: 父块最大字符数（章节级上下文）
            parent_chunk_overlap: 父块重叠字符数
            child_chunk_size: 子块最大字符数（条款级）
            child_chunk_overlap: 子块重叠字符数
        """
        self.parent_chunk_size = parent_chunk_size
        self.parent_chunk_overlap = parent_chunk_overlap
        self.child_chunk_size = child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap

    def split(self, text: str) -> List[Dict]:
        """
        将文本分割成父子块。

        策略：
        1. 先按章节标题拆父块
        2. 每个父块内按条款编号拆子块
        3. 无结构文本回退到固定字数切分

        Returns:
            [{"parent_id", "parent_content", "child_id", "child_content"}, ...]
        """
        if not text or not text.strip():
            return []

        # 1. 按章节标题拆父块
        sections = _split_by_sections(text)

        if len(sections) < 2:
            # 没有章节标题，尝试按条款拆
            clauses = _split_by_clauses(text)
            if len(clauses) >= 2:
                # 有条款但没有章节标题，按条款聚合成父块
                logger.info(f"文档无章节标题，使用条款聚合分块: {len(clauses)} 个条款")
                return self._build_from_clauses(clauses)
            else:
                # 完全无结构，回退到固定字数切分
                logger.warning("文档无结构特征，使用回退分块方案（固定字数切分）")
                return self._fallback_split(text)

        logger.info(f"文档按章节标题分块: {len(sections)} 个章节")

        # 2. 每个章节内按条款拆子块
        chunks = []
        for p_idx, section_text in enumerate(sections):
            parent_id = f"p{p_idx}"

            # 章节内按条款拆子块
            clauses = _split_by_clauses(section_text)

            if len(clauses) < 2:
                # 章节内无条款编号，回退到段落/句子切分
                logger.debug(f"章节 {parent_id} 无条款编号，使用回退分块")
                child_texts = _fallback_split(
                    section_text,
                    chunk_size=self.child_chunk_size,
                    overlap=self.child_chunk_overlap,
                )
            else:
                child_texts = clauses

            # 过滤空子块
            child_texts = [c.strip() for c in child_texts if c.strip()]

            for c_idx, child_content in enumerate(child_texts):
                child_id = f"{parent_id}_c{c_idx}"
                chunks.append({
                    "parent_id": parent_id,
                    "parent_content": section_text,
                    "child_id": child_id,
                    "child_content": child_content,
                })

        return chunks

    def _build_from_clauses(self, clauses: List[str]) -> List[Dict]:
        """
        有条款但无章节标题时，按条款聚合成父块。
        每个父块包含若干连续条款，总大小不超过 parent_chunk_size。
        """
        chunks = []
        p_idx = 0
        current_parent_clauses = []
        current_parent_size = 0

        for clause in clauses:
            clause_len = len(clause)

            # 如果当前父块已满，生成并开启新父块
            if current_parent_size + clause_len > self.parent_chunk_size and current_parent_clauses:
                parent_id = f"p{p_idx}"
                parent_content = '\n\n'.join(current_parent_clauses)

                for c_idx, child_content in enumerate(current_parent_clauses):
                    child_id = f"{parent_id}_c{c_idx}"
                    chunks.append({
                        "parent_id": parent_id,
                        "parent_content": parent_content,
                        "child_id": child_id,
                        "child_content": child_content,
                    })

                p_idx += 1
                current_parent_clauses = []
                current_parent_size = 0

            current_parent_clauses.append(clause)
            current_parent_size += clause_len

        # 处理最后一个父块
        if current_parent_clauses:
            parent_id = f"p{p_idx}"
            parent_content = '\n\n'.join(current_parent_clauses)
            for c_idx, child_content in enumerate(current_parent_clauses):
                child_id = f"{parent_id}_c{c_idx}"
                chunks.append({
                    "parent_id": parent_id,
                    "parent_content": parent_content,
                    "child_id": child_id,
                    "child_content": child_content,
                })

        return chunks

    def _fallback_split(self, text: str) -> List[Dict]:
        """完全无结构文本的回退方案"""
        parent_texts = _fallback_split(
            text,
            chunk_size=self.parent_chunk_size,
            overlap=self.parent_chunk_overlap,
        )

        chunks = []
        for p_idx, parent_content in enumerate(parent_texts):
            parent_id = f"p{p_idx}"
            child_texts = _fallback_split(
                parent_content,
                chunk_size=self.child_chunk_size,
                overlap=self.child_chunk_overlap,
            )
            for c_idx, child_content in enumerate(child_texts):
                child_id = f"{parent_id}_c{c_idx}"
                chunks.append({
                    "parent_id": parent_id,
                    "parent_content": parent_content,
                    "child_id": child_id,
                    "child_content": child_content,
                })
        return chunks

    def split_simple(self, text: str) -> List[str]:
        """简单分块（仅父块）"""
        if not text or not text.strip():
            return []

        sections = _split_by_sections(text)
        if sections:
            return [s.strip() for s in sections if s.strip()]

        clauses = _split_by_clauses(text)
        if clauses:
            return [c.strip() for c in clauses if c.strip()]

        return _fallback_split(text, chunk_size=self.parent_chunk_size, overlap=self.parent_chunk_overlap)

    def evaluate_quality(self, chunks: List[Dict]) -> Dict:
        """评估分块质量"""
        if not chunks:
            return {"quality": "empty", "details": {}}

        child_sizes = [len(chunk["child_content"]) for chunk in chunks]
        parent_ids = set(c["parent_id"] for c in chunks)
        parent_sizes = [len(chunk["parent_content"]) for chunk in chunks]

        avg_child_size = sum(child_sizes) / len(child_sizes)
        avg_parent_size = sum(parent_sizes) / len(parent_ids)

        too_short = sum(1 for s in child_sizes if s < 30)
        too_long = sum(1 for s in child_sizes if s > 800)

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
