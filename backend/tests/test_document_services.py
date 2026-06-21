"""
文档处理服务测试
===============
基于真实 API 测试：
- DocumentParser：parse(), validate_file(), detect_language()
- TextSplitter：split(), split_simple(), evaluate_quality()
- DocumentProcessor：process_document()（需外部服务）

运行：pytest tests/test_document_services.py -v -s -o "addopts="
"""

import pytest
import os
from unittest.mock import patch, Mock

from app.services.document_parser import DocumentParser
from app.services.text_splitter import TextSplitter


class TestDocumentParserValidate:
    """文件校验"""

    def test_reject_nonexistent_file(self):
        result = DocumentParser.validate_file("/nonexistent/file.pdf")
        assert not result["valid"]

    def test_reject_bad_extension(self, tmp_path):
        f = tmp_path / "test.exe"
        f.write_bytes(b"data")
        result = DocumentParser.validate_file(str(f))
        assert not result["valid"]

    def test_accept_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        result = DocumentParser.validate_file(str(f))
        assert result["valid"]
        assert result["size"] == 11

    def test_accept_pdf_extension(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        result = DocumentParser.validate_file(str(f))
        assert result["valid"]


class TestDocumentParserParse:
    """文档解析"""

    def test_parse_txt_via_unified_parse(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("第一行内容\n第二行内容\n", encoding="utf-8")
        text = DocumentParser.parse(str(f))
        assert "第一行内容" in text
        assert "第二行内容" in text

    def test_parse_empty_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("", encoding="utf-8")
        text = DocumentParser.parse(str(f))
        assert text == ""

    def test_parse_rejects_unsupported(self):
        with pytest.raises(ValueError):
            DocumentParser.parse("test.xls")


class TestDocumentParserLanguage:
    """语言检测"""

    def test_detect_chinese(self):
        lang = DocumentParser.detect_language("这是中文测试文本" * 10)
        assert lang == "zh-cn" or lang.startswith("zh")

    def test_detect_short_text(self):
        assert DocumentParser.detect_language("Hi") == "unknown"


class TestTextSplitter:
    """父子分块器"""

    @pytest.fixture
    def splitter(self):
        return TextSplitter()

    @pytest.fixture
    def long_text(self):
        return "第一段内容。\n\n第二段内容。\n\n第三段内容。" * 20

    def test_split_returns_dicts(self, splitter, long_text):
        chunks = splitter.split(long_text)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for c in chunks:
            assert "parent_id" in c
            assert "parent_content" in c
            assert "child_id" in c
            assert "child_content" in c

    def test_split_simple_returns_strings(self, splitter, long_text):
        chunks = splitter.split_simple(long_text)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_split_empty(self, splitter):
        assert splitter.split("") == []
        assert splitter.split("   ") == []
        assert splitter.split_simple("") == []

    def test_split_small_text(self, splitter):
        # 使用 ≥30 字符的文本，避免被清洗流水线拦截
        # （min_effective_chars_per_page=30）
        chunks = splitter.split("这是一个短文本测试用例，用于验证文本分块器对较小文本的正确处理能力。短文本")
        assert len(chunks) >= 1
        assert "短文本" in chunks[0]["parent_content"]

    def test_evaluate_quality_good(self, splitter, long_text):
        chunks = splitter.split(long_text)
        result = splitter.evaluate_quality(chunks)
        assert result["quality"] in ("good", "fair", "poor")
        assert result["total_children"] > 0

    def test_evaluate_quality_empty(self, splitter):
        result = splitter.evaluate_quality([])
        assert result["quality"] == "empty"


class TestDocumentParserRealFile:
    """真实 PDF 文件解析 — 使用项目根目录的学生手册"""

    def test_parse_student_handbook(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        handbook = os.path.join(project_root, "2025学生手册.pdf")
        if not os.path.exists(handbook):
            pytest.skip(f"学生手册文件不存在: {handbook}")

        text = DocumentParser.parse(handbook)
        assert len(text) > 1000
        assert "上海交通大学" in text or "本科生" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
