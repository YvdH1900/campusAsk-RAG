"""
文本分块服务（父子分块）
======================
使用 Parent-Child Chunking 策略：
1. 父块：较大块（800字符），保留完整上下文
2. 子块：较小块（200字符），用于精确向量检索
3. 检索时：子块匹配，返回对应父块作为上下文
"""

from typing import List, Dict, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextSplitter:
    """父子文本分块器"""

    def __init__(
        self,
        parent_chunk_size: int = 800,
        parent_chunk_overlap: int = 100,
        child_chunk_size: int = 200,
        child_chunk_overlap: int = 30,
    ):
        """
        初始化父子文本分块器
        
        Args:
            parent_chunk_size: 父块最大字符数
            parent_chunk_overlap: 父块重叠字符数
            child_chunk_size: 子块最大字符数
            child_chunk_overlap: 子块重叠字符数
        """
        separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_chunk_overlap,
            length_function=len,
            separators=separators,
        )
        
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
            length_function=len,
            separators=separators,
        )

    def split(self, text: str) -> List[Dict]:
        """
        将文本分割成父子块
        
        Args:
            text: 要分割的文本
            
        Returns:
            包含父子块关系的列表，格式:
            [
                {
                    "parent_id": "p0",
                    "parent_content": "父块内容",
                    "child_id": "p0_c0",
                    "child_content": "子块内容",
                },
                ...
            ]
        """
        if not text or not text.strip():
            return []

        # 1. 先分割成父块
        parent_chunks = self.parent_splitter.split_text(text)
        parent_chunks = [chunk.strip() for chunk in parent_chunks if chunk.strip()]

        if not parent_chunks:
            return []

        # 2. 每个父块再分割成子块
        result = []
        for p_idx, parent_content in enumerate(parent_chunks):
            parent_id = f"p{p_idx}"
            
            child_chunks = self.child_splitter.split_text(parent_content)
            child_chunks = [chunk.strip() for chunk in child_chunks if chunk.strip()]
            
            for c_idx, child_content in enumerate(child_chunks):
                child_id = f"{parent_id}_c{c_idx}"
                result.append({
                    "parent_id": parent_id,
                    "parent_content": parent_content,
                    "child_id": child_id,
                    "child_content": child_content,
                })

        return result

    def split_simple(self, text: str) -> List[str]:
        """
        简单分块（仅父块），用于不需要子块的场景
        
        Args:
            text: 要分割的文本
            
        Returns:
            父块列表
        """
        if not text or not text.strip():
            return []

        chunks = self.parent_splitter.split_text(text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def evaluate_quality(self, chunks: List[Dict]) -> Dict:
        """
        评估分块质量
        
        Args:
            chunks: 父子块列表
            
        Returns:
            质量评估结果
        """
        if not chunks:
            return {"quality": "empty", "details": {}}

        child_sizes = [len(chunk["child_content"]) for chunk in chunks]
        parent_sizes = [len(chunk["parent_content"]) for chunk in chunks]
        
        avg_child_size = sum(child_sizes) / len(child_sizes)
        avg_parent_size = sum(parent_sizes) / len(set(c["parent_id"] for c in chunks))
        
        too_short = sum(1 for s in child_sizes if s < 50)
        too_long = sum(1 for s in child_sizes if s > 500)
        
        # 质量评级
        if too_short > len(child_sizes) * 0.3 or too_long > len(child_sizes) * 0.1:
            quality = "poor"
        elif too_short > len(child_sizes) * 0.1:
            quality = "fair"
        else:
            quality = "good"

        return {
            "quality": quality,
            "total_children": len(child_sizes),
            "total_parents": len(set(c["parent_id"] for c in chunks)),
            "avg_child_size": round(avg_child_size, 1),
            "avg_parent_size": round(avg_parent_size, 1),
            "too_short": too_short,
            "too_long": too_long,
        }
