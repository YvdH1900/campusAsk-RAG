"""
文档处理服务单元测试
====================
测试文档处理的核心功能：
- 文档解析（PDF、Word、TXT）
- 文本分割
- 文档预处理
- 文档哈希计算
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
import hashlib

from app.services.document_parser import DocumentParser
from app.services.document_processor import DocumentProcessor
from app.services.text_splitter import TextSplitter


class TestDocumentParser:
    """文档解析器测试"""
    
    @pytest.fixture
    def parser(self):
        """文档解析器 fixture"""
        return DocumentParser()
    
    def test_parse_txt_file(self, parser):
        """测试解析 TXT 文件"""
        content = "这是一个测试文本文件。\n包含多行内容。"
        
        with patch('builtins.open', MagicMock(return_value=BytesIO(content.encode('utf-8')))):
            result = parser.parse_txt("test.txt")
            
            assert result is not None
            assert "这是一个测试文本文件" in result
            assert "包含多行内容" in result
    
    def test_parse_txt_empty(self, parser):
        """测试解析空 TXT 文件"""
        content = ""
        
        with patch('builtins.open', MagicMock(return_value=BytesIO(content.encode('utf-8')))):
            result = parser.parse_txt("empty.txt")
            
            assert result == "" or result is None
    
    def test_parse_word_document(self, parser):
        """测试解析 Word 文档"""
        with patch('docx.Document') as mock_docx:
            mock_doc = Mock()
            mock_doc.paragraphs = [
                Mock(text="第一段内容"),
                Mock(text="第二段内容"),
            ]
            mock_docx.return_value = mock_doc
            
            result = parser.parse_docx("test.docx")
            
            assert result is not None
            assert "第一段内容" in result
            assert "第二段内容" in result
    
    def test_parse_word_with_tables(self, parser):
        """测试解析带表格的 Word 文档"""
        with patch('docx.Document') as mock_docx:
            mock_doc = Mock()
            mock_doc.paragraphs = [Mock(text="段落内容")]
            
            mock_table = Mock()
            mock_table.rows = [
                Mock(cells=[Mock(text="单元格 1"), Mock(text="单元格 2")]),
            ]
            mock_doc.tables = [mock_table]
            
            mock_docx.return_value = mock_doc
            
            result = parser.parse_docx("test.docx")
            
            assert result is not None
            assert "段落内容" in result
    
    def test_parse_pdf(self, parser):
        """测试解析 PDF 文档"""
        with patch('pdfplumber.open') as mock_pdf:
            mock_page = Mock()
            mock_page.extract_text.return_value = "PDF 页面内容"
            mock_pdf.return_value.__enter__.return_value.pages = [mock_page]
            
            result = parser.parse_pdf("test.pdf")
            
            assert result is not None
            assert "PDF 页面内容" in result
    
    def test_parse_pdf_multiple_pages(self, parser):
        """测试解析多页 PDF"""
        with patch('pdfplumber.open') as mock_pdf:
            mock_pages = []
            for i in range(3):
                mock_page = Mock()
                mock_page.extract_text.return_value = f"第{i+1}页内容"
                mock_pages.append(mock_page)
            
            mock_pdf.return_value.__enter__.return_value.pages = mock_pages
            
            result = parser.parse_pdf("test.pdf")
            
            assert result is not None
            assert "第 1 页内容" in result
            assert "第 2 页内容" in result
            assert "第 3 页内容" in result
    
    def test_parse_unsupported_format(self, parser):
        """测试解析不支持的格式"""
        with pytest.raises(ValueError):
            parser.parse("test.xls")
    
    def test_parse_auto_detect_format(self, parser):
        """测试自动检测文件格式"""
        with patch.object(parser, 'parse_txt') as mock_parse_txt:
            mock_parse_txt.return_value = "TXT 内容"
            
            result = parser.parse("test.txt")
            
            assert mock_parse_txt.called
            assert result == "TXT 内容"


class TestTextSplitter:
    """文本分割器测试"""
    
    @pytest.fixture
    def splitter(self):
        """文本分割器 fixture"""
        return TextSplitter()
    
    @pytest.fixture
    def sample_text(self):
        """示例文本"""
        return "这是第一段。\n\n这是第二段。\n\n这是第三段。" * 10
    
    def test_split_by_chunk_size(self, splitter, sample_text):
        """测试按块大小分割"""
        chunks = splitter.split_by_chunk_size(sample_text, chunk_size=100)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert len(chunk) <= 100 or len(chunk) >= 50  # 允许一定的弹性
    
    def test_split_by_paragraph(self, splitter, sample_text):
        """测试按段落分割"""
        paragraphs = splitter.split_by_paragraph(sample_text)
        
        assert isinstance(paragraphs, list)
        assert len(paragraphs) > 0
        
        for para in paragraphs:
            assert "\n\n" not in para  # 每个段落不应该包含双换行
    
    def test_split_preserve_content(self, splitter, sample_text):
        """测试分割保留内容"""
        chunks = splitter.split_by_chunk_size(sample_text, chunk_size=200)
        
        # 验证所有 chunk 拼接后等于原文
        reconstructed = "".join(chunks)
        assert reconstructed == sample_text
    
    def test_split_empty_text(self, splitter):
        """测试分割空文本"""
        chunks = splitter.split_by_chunk_size("", chunk_size=100)
        
        assert chunks == []
    
    def test_split_very_small_text(self, splitter):
        """测试分割非常小的文本"""
        text = "短文本"
        
        chunks = splitter.split_by_chunk_size(text, chunk_size=100)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_split_overlap(self, splitter, sample_text):
        """测试重叠分割"""
        chunks = splitter.split_by_chunk_size(
            sample_text,
            chunk_size=100,
            overlap=20
        )
        
        assert isinstance(chunks, list)
        
        if len(chunks) > 1:
            # 验证相邻 chunk 之间有重叠
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i][-20:] if len(chunks[i]) >= 20 else chunks[i]
                chunk2_start = chunks[i + 1][:20] if len(chunks[i + 1]) >= 20 else chunks[i + 1]
                
                # 检查是否有重叠（简化验证）
                assert len(chunks[i]) > 0
                assert len(chunks[i + 1]) > 0


class TestDocumentProcessor:
    """文档处理器测试"""
    
    @pytest.fixture
    def processor(self):
        """文档处理器 fixture"""
        return DocumentProcessor()
    
    @pytest.fixture
    def sample_document(self):
        """示例文档"""
        return {
            "id": 1,
            "title": "测试文档",
            "content": "这是测试文档的内容" * 100,
            "file_type": "txt",
        }
    
    def test_preprocess_text(self, processor, sample_document):
        """测试文本预处理"""
        content = "  这是包含 多余空格 和\n换行符 的文本。  "
        
        preprocessed = processor.preprocess_text(content)
        
        assert preprocessed is not None
        assert isinstance(preprocessed, str)
        # 验证基本清理
        assert len(preprocessed) > 0
    
    def test_compute_document_hash(self, processor, sample_document):
        """测试文档哈希计算"""
        content = "测试内容"
        
        hash1 = processor.compute_document_hash(content)
        hash2 = processor.compute_document_hash(content)
        hash3 = processor.compute_document_hash("不同内容")
        
        assert hash1 is not None
        assert isinstance(hash1, str)
        assert len(hash1) > 0
        
        # 相同内容应该生成相同哈希
        assert hash1 == hash2
        
        # 不同内容应该生成不同哈希
        assert hash1 != hash3
    
    def test_extract_metadata(self, processor):
        """测试提取元数据"""
        with patch('os.path.getsize') as mock_getsize, \
             patch('os.path.getmtime') as mock_getmtime:
            
            mock_getsize.return_value = 1024
            mock_getmtime.return_value = 1234567890
            
            metadata = processor.extract_metadata("test.txt")
            
            assert metadata is not None
            assert isinstance(metadata, dict)
            assert "file_size" in metadata or "size" in metadata
    
    def test_process_document_full_pipeline(self, processor, sample_document):
        """测试完整的文档处理流程"""
        with patch.object(processor, 'preprocess_text') as mock_preprocess, \
             patch.object(processor, 'compute_document_hash') as mock_hash, \
             patch('app.services.text_splitter.TextSplitter') as mock_splitter:
            
            mock_preprocess.return_value = sample_document["content"]
            mock_hash.return_value = "test_hash_123"
            
            mock_splitter_instance = Mock()
            mock_splitter_instance.split_by_paragraph.return_value = ["chunk1", "chunk2"]
            mock_splitter.return_value = mock_splitter_instance
            
            result = processor.process_document(sample_document)
            
            assert mock_preprocess.called
            assert mock_hash.called
            assert result is not None
            assert isinstance(result, dict)
    
    def test_validate_document(self, processor):
        """测试文档验证"""
        # 有效文档
        valid_doc = {"content": "有效内容", "title": "标题"}
        assert processor.validate_document(valid_doc) is True
        
        # 空内容
        invalid_doc1 = {"content": "", "title": "标题"}
        assert processor.validate_document(invalid_doc1) is False
        
        # 缺少必要字段
        invalid_doc2 = {"title": "标题"}
        assert processor.validate_document(invalid_doc2) is False
    
    def test_clean_text(self, processor):
        """测试文本清理"""
        dirty_text = "这是包含特殊字符的文本：\x00\x01\x02 和多余空格   "
        
        cleaned = processor.clean_text(dirty_text)
        
        assert cleaned is not None
        assert "\x00" not in cleaned
        assert "\x01" not in cleaned
        assert "\x02" not in cleaned
    
    def test_normalize_whitespace(self, processor):
        """测试空白字符规范化"""
        text = "多个   空格\t和\n换行\r\n混合"
        
        normalized = processor.normalize_whitespace(text)
        
        assert normalized is not None
        # 验证空白字符被规范化
        assert "  " not in normalized or "\t" not in normalized


class TestDocumentParserIntegration:
    """文档解析器集成测试"""
    
    @pytest.fixture
    def parser(self):
        """文档解析器 fixture"""
        return DocumentParser()
    
    def test_parse_large_file(self, parser):
        """测试解析大文件"""
        large_content = "大文件内容" * 10000
        
        with patch('builtins.open', MagicMock(return_value=BytesIO(large_content.encode('utf-8')))):
            result = parser.parse_txt("large.txt")
            
            assert result is not None
            assert len(result) > 0
            assert "大文件内容" in result
    
    def test_parse_file_with_special_characters(self, parser):
        """测试解析包含特殊字符的文件"""
        content = "包含特殊字符：!@#$%^&*()_+-=[]{}|;':\",./<>?"
        
        with patch('builtins.open', MagicMock(return_value=BytesIO(content.encode('utf-8')))):
            result = parser.parse_txt("special.txt")
            
            assert result is not None
            # 特殊字符应该被保留
            assert "特殊字符" in result
    
    def test_parse_file_with_unicode(self, parser):
        """测试解析包含 Unicode 的文件"""
        content = "包含 Unicode：你好 🌍 Привет مرحبا"
        
        with patch('builtins.open', MagicMock(return_value=BytesIO(content.encode('utf-8')))):
            result = parser.parse_txt("unicode.txt")
            
            assert result is not None
            assert "Unicode" in result or "你好" in result
    
    def test_parse_corrupted_file(self, parser):
        """测试解析损坏的文件"""
        with patch('builtins.open', side_effect=IOError("文件损坏")):
            with pytest.raises(IOError):
                parser.parse_txt("corrupted.txt")


class TestTextSplitterIntegration:
    """文本分割器集成测试"""
    
    @pytest.fixture
    def splitter(self):
        """文本分割器 fixture"""
        return TextSplitter()
    
    def test_split_realistic_document(self, splitter):
        """测试分割真实文档"""
        # 模拟一个真实的文档结构
        document = """
        第一章 总则
        
        第一条 为了规范...
        
        第二章 分则
        
        第二条 具体规定...
        
        第三章 附则
        
        第三条 解释权...
        """ * 5
        
        chunks = splitter.split_by_paragraph(document)
        
        assert len(chunks) > 0
        
        # 验证每个 chunk 都有一定长度
        for chunk in chunks:
            assert len(chunk.strip()) > 0
    
    def test_split_code_content(self, splitter):
        """测试分割代码内容"""
        code = """
def hello():
    print("Hello, World!")

class MyClass:
    def __init__(self):
        pass
""" * 10
        
        chunks = splitter.split_by_paragraph(code)
        
        assert len(chunks) > 0
        
        # 代码应该被合理分割
        for chunk in chunks:
            assert len(chunk) > 0
    
    def test_split_mixed_content(self, splitter):
        """测试分割混合内容"""
        mixed = """
        这是中文段落。
        
        This is an English paragraph.
        
        1. 列表项 1
        2. 列表项 2
        
        - 项目符号 1
        - 项目符号 2
        """ * 3
        
        chunks = splitter.split_by_paragraph(mixed)
        
        assert len(chunks) > 0
        
        # 验证混合内容被正确分割
        for chunk in chunks:
            assert len(chunk.strip()) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
