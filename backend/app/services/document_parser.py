"""
文档解析服务
====================
支持多种文档格式的文本提取：
1. PDF - 使用 pdfplumber 解析（支持流式按页解析）
2. DOCX - 使用 python-docx 解析
3. TXT - 直接读取
4. MD - 直接读取

支持：
- 文件类型校验（python-magic）
- 表格特殊处理
- 多语言自动检测
- 流式解析（按页/章节）
"""

import os
import re
import logging

# python-magic 在 Windows 上依赖 libmagic.dll，通常不可用
# 使用扩展名回退方案保证跨平台兼容
try:
    import magic
    _HAS_MAGIC = True
except (ImportError, OSError):
    _HAS_MAGIC = False
    magic = None

logger = logging.getLogger(__name__)
from typing import Optional, Generator
from langdetect import detect, LangDetectException
from pdfplumber import open as pdf_open
from docx import Document as DocxDocument
from docx.oxml.ns import qn


class DocumentParser:
    """文档解析器"""

    # 支持的文件扩展名
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}
    
    # 最大文件大小（100MB）
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    # MIME 类型映射
    MIME_TYPE_MAP = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".txt": "text/plain",
        ".md": "text/plain",
    }

    @classmethod
    def validate_file(cls, file_path: str) -> dict:
        """
        校验文件类型和大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            校验结果 {"valid": bool, "mime_type": str, "size": int, "error": str}
        """
        if not os.path.exists(file_path):
            return {"valid": False, "error": "文件不存在"}
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > cls.MAX_FILE_SIZE:
            return {"valid": False, "error": f"文件大小超过限制 ({cls.MAX_FILE_SIZE / 1024 / 1024}MB)"}
        
        # 检查扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            return {"valid": False, "error": f"不支持的文件格式: {ext}"}
        
        # 检查真实 MIME 类型
        if _HAS_MAGIC and magic:
            mime = magic.from_file(file_path, mime=True)
            expected_mime = cls.MIME_TYPE_MAP.get(ext)
            
            if expected_mime and mime != expected_mime:
                # 允许 text/plain 的变体
                if not (expected_mime == "text/plain" and mime.startswith("text/")):
                    return {"valid": False, "error": f"文件类型不匹配，期望 {expected_mime}，实际 {mime}"}
        else:
            # Windows 上 magic 不可用，使用扩展名作为 MIME 类型
            mime = cls.MIME_TYPE_MAP.get(ext, "application/octet-stream")
            logger.debug("python-magic 不可用，使用扩展名进行文件类型校验")
        
        return {
            "valid": True,
            "mime_type": mime,
            "size": file_size,
        }

    @staticmethod
    def detect_language(text: str) -> str:
        """
        自动检测文本语言
        
        Args:
            text: 文本内容
            
        Returns:
            语言代码 (zh, en, ja, 等)
        """
        if not text or len(text.strip()) < 10:
            return "unknown"
        
        try:
            # 取前 1000 字符用于检测
            sample = text[:1000]
            lang = detect(sample)
            return lang
        except LangDetectException:
            return "unknown"

    @staticmethod
    def parse(file_path: str) -> str:
        """
        解析文档并返回纯文本内容
        
        Args:
            file_path: 文档文件路径
            
        Returns:
            提取的纯文本内容
        """
        # 校验文件
        validation = DocumentParser.validate_file(file_path)
        if not validation["valid"]:
            raise ValueError(f"文件校验失败: {validation['error']}")
        
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            return DocumentParser._parse_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return DocumentParser._parse_docx(file_path)
        elif ext == ".txt":
            return DocumentParser._parse_txt(file_path)
        elif ext == ".md":
            return DocumentParser._parse_md(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    @staticmethod
    def parse_stream(file_path: str, chunk_pages: int = 5) -> Generator[str, None, None]:
        """
        流式解析文档（按页/章节分批返回）
        
        Args:
            file_path: 文档文件路径
            chunk_pages: 每批处理的页数
            
        Yields:
            每批文本
        """
        validation = DocumentParser.validate_file(file_path)
        if not validation["valid"]:
            raise ValueError(f"文件校验失败: {validation['error']}")
        
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            yield from DocumentParser._parse_pdf_stream(file_path, chunk_pages)
        elif ext in [".docx", ".doc"]:
            yield from DocumentParser._parse_docx_stream(file_path, chunk_pages)
        else:
            # TXT/MD 直接返回全文
            yield DocumentParser.parse(file_path)

    @staticmethod
    def _parse_pdf(file_path: str) -> str:
        """解析 PDF 文件（带清洗：去页眉页脚、页码、控制字符、重复行）"""
        text_parts = []
        seen_headers: set = set()  # 用于跨页去重页眉页脚

        with pdf_open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if not page_text:
                    continue

                page_lines = page_text.split("\n")
                cleaned_lines = []

                for line in page_lines:
                    stripped = line.strip()

                    # 1. 跳过空行
                    if not stripped:
                        continue

                    # 2. 去除控制字符和不可见字符
                    stripped = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", stripped).strip()
                    if not stripped:
                        continue

                    # 3. 去除纯页码行（多种格式）
                    if re.match(r"^\d{1,4}$", stripped):
                        continue
                    if re.match(r"^[-—]\s*\d{1,4}\s*[-—]$", stripped):
                        continue
                    if re.match(r"^第\s*\d{1,4}\s*页$", stripped):
                        continue
                    if re.match(r"^\d{1,4}\s*/\s*\d{1,4}$", stripped):
                        continue

                    # 4. 去除过短的行（单字符、纯标点）
                    if len(stripped) <= 1:
                        continue

                    # 5. 去除页眉页脚（短行 + 跨页重复出现）
                    if len(stripped) < 30:
                        if stripped in seen_headers:
                            continue  # 已见过，跳过（页眉/页脚）
                        seen_headers.add(stripped)

                    # 6. 去除纯数字/纯标点行
                    if re.match(r"^[\d\s\.\-—、,，。]+$", stripped):
                        continue

                    cleaned_lines.append(stripped)

                if cleaned_lines:
                    text_parts.append("\n".join(cleaned_lines))

        full_text = "\n\n".join(text_parts)

        # 最终清理：合并连续空行、去除首尾空白
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = full_text.strip()

        return full_text

    @staticmethod
    def _parse_pdf_stream(file_path: str, chunk_pages: int) -> Generator[str, None, None]:
        """流式解析 PDF 文件"""
        with pdf_open(file_path) as pdf:
            batch = []
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    batch.append(page_text)
                
                # 每 chunk_pages 页返回一次
                if len(batch) >= chunk_pages:
                    yield "\n\n".join(batch)
                    batch = []
            
            # 返回剩余内容
            if batch:
                yield "\n\n".join(batch)

    @staticmethod
    def _parse_docx(file_path: str) -> str:
        """解析 DOCX 文件（支持表格处理）"""
        doc = DocxDocument(file_path)
        text_parts = []
        
        for element in doc.element.body:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            if tag == 'p':
                # 段落
                para = None
                for p in doc.paragraphs:
                    if p._element == element:
                        para = p
                        break
                if para and para.text.strip():
                    text_parts.append(para.text)
            
            elif tag == 'tbl':
                # 表格（保持结构）
                table_text = DocumentParser._extract_table_text(element, doc)
                if table_text:
                    text_parts.append(table_text)
        
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_table_text(table_element, doc) -> str:
        """
        提取表格文本并保持结构
        
        Args:
            table_element: 表格 XML 元素
            doc: DOCX 文档对象
            
        Returns:
            格式化的表格文本
        """
        rows = []
        for tr in table_element.findall('.//' + qn('w:tr')):
            cells = []
            for tc in tr.findall('.//' + qn('w:tc')):
                cell_text = ''.join(node.text or '' for node in tc.iter() if node.text)
                cells.append(cell_text.strip())
            if cells:
                rows.append(" | ".join(cells))
        
        if not rows:
            return ""
        
        # 添加表头分隔符
        if len(rows) > 1:
            header_parts = ["---"] * len(rows[0].split(" | "))
            rows.insert(1, " | ".join(header_parts))
        
        return "\n".join(rows)

    @staticmethod
    def _parse_docx_stream(file_path: str, chunk_pages: int) -> Generator[str, None, None]:
        """流式解析 DOCX 文件"""
        doc = DocxDocument(file_path)
        batch = []
        count = 0
        
        for element in doc.element.body:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            if tag == 'p':
                for p in doc.paragraphs:
                    if p._element == element and p.text.strip():
                        batch.append(p.text)
                        count += 1
                        break
            
            elif tag == 'tbl':
                table_text = DocumentParser._extract_table_text(element, doc)
                if table_text:
                    batch.append(table_text)
                    count += 1
            
            if count >= chunk_pages:
                yield "\n\n".join(batch)
                batch = []
                count = 0
        
        if batch:
            yield "\n\n".join(batch)

    @staticmethod
    def _parse_txt(file_path: str) -> str:
        """解析 TXT 文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _parse_md(file_path: str) -> str:
        """解析 MD 文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
