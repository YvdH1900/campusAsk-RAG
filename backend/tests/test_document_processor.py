"""
文档处理器真实环境测试
====================
测试文档上传→解析→分块→向量化→入库的完整流程
需要 MySQL + Milvus + Embedding API 可用
"""

import pytest
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models import Document
from app.services.document_processor import DocumentProcessor
from app.services.document_parser import DocumentParser
from app.services.text_splitter import TextSplitter


@pytest.fixture
def db():
    """数据库会话"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def processor():
    """文档处理器实例"""
    return DocumentProcessor()


@pytest.mark.real
class TestDocumentProcessorReal:
    """文档处理器真实环境测试"""

    def test_process_txt_document(self, db, processor, tmp_path):
        """
        测试处理 TXT 文档
        流程：创建文件 → 创建 Document 记录 → process_document → 验证状态和向量
        """
        # 1. 创建测试文件
        test_file = tmp_path / "test_doc.txt"
        test_file.write_text(
            "上海交通大学的校训是饮水思源，爱国荣校。\n"
            "这体现了学校的精神内核和办学传统。\n"
            "学校成立于1896年，是中国历史最悠久的高等学府之一。\n"
            '学校秉承"起点高、基础厚、要求严、重实践"的办学传统。\n',
            encoding="utf-8",
        )

        # 2. 创建 Document 记录
        doc = Document(
            filename="test_doc.txt",
            file_path=str(test_file),
            file_size=test_file.stat().st_size,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # 3. 处理文档
        processor.process_document(doc, db)

        # 4. 验证文档状态
        db.refresh(doc)
        assert doc.status == "completed", f"文档处理失败，状态: {doc.status}"

        # 5. 验证向量入库（通过向量一致性检查）
        from app.services.vector_consistency import VectorConsistencyChecker
        checker = VectorConsistencyChecker()
        result = checker.check_consistency(db)
        assert result["is_consistent"], "向量库不一致"

        # 6. 清理
        processor.delete_document_vectors(doc.id, db)
        db.execute(text(f"DELETE FROM documents WHERE id = {doc.id}"))
        db.commit()

    def test_process_empty_document(self, db, processor, tmp_path):
        """
        测试处理空文档
        预期：status=failed
        """
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding="utf-8")

        doc = Document(
            filename="empty.txt",
            file_path=str(test_file),
            file_size=0,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        with pytest.raises(ValueError, match="文档内容为空"):
            processor.process_document(doc, db)

        db.refresh(doc)
        assert doc.status == "failed"

        # 清理
        db.execute(text(f"DELETE FROM documents WHERE id = {doc.id}"))
        db.commit()

    def test_process_nonexistent_file(self, db, processor):
        """
        测试处理不存在的文件
        预期：status=failed
        """
        doc = Document(
            filename="nonexistent.pdf",
            file_path="/nonexistent/path/file.pdf",
            file_size=0,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        with pytest.raises(Exception):
            processor.process_document(doc, db)

        db.refresh(doc)
        assert doc.status == "failed"

        # 清理
        db.execute(text(f"DELETE FROM documents WHERE id = {doc.id}"))
        db.commit()

    def test_process_rollback_on_vector_failure(self, db, processor, tmp_path):
        """
        测试向量入库失败时回滚
        模拟：向量存储失败 → 文档状态回滚为 failed
        """
        test_file = tmp_path / "test_rollback.txt"
        test_file.write_text("测试回滚的内容。" * 100, encoding="utf-8")

        doc = Document(
            filename="test_rollback.txt",
            file_path=str(test_file),
            file_size=test_file.stat().st_size,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Mock 向量存储失败
        from unittest.mock import patch
        with patch.object(processor, "_get_vector_store") as mock_vs:
            mock_vs.return_value.insert.side_effect = Exception("向量存储失败")
            with pytest.raises(Exception, match="向量存储失败"):
                processor.process_document(doc, db)

        db.refresh(doc)
        assert doc.status == "failed"

        # 清理
        db.execute(text(f"DELETE FROM documents WHERE id = {doc.id}"))
        db.commit()

    def test_delete_document_vectors(self, db, processor, tmp_path):
        """
        测试删除文档向量
        流程：处理文档 → 删除向量 → 验证向量已删除
        """
        test_file = tmp_path / "test_delete.txt"
        test_file.write_text("测试删除向量的内容。" * 50, encoding="utf-8")

        doc = Document(
            filename="test_delete.txt",
            file_path=str(test_file),
            file_size=test_file.stat().st_size,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # 处理文档
        processor.process_document(doc, db)
        db.refresh(doc)
        assert doc.status == "completed"

        # 删除向量
        processor.delete_document_vectors(doc.id, db)

        # 验证向量已删除（通过向量一致性检查）
        from app.services.vector_consistency import VectorConsistencyChecker
        checker = VectorConsistencyChecker()
        result = checker.check_consistency(db)
        # 文档记录还在，但向量已删除，应该检测到不一致
        assert doc.id in result.get("missing_documents", []), "向量应该被删除"

        # 清理
        db.execute(text(f"DELETE FROM documents WHERE id = {doc.id}"))
        db.commit()

    def test_progress_callback(self, db, processor, tmp_path):
        """
        测试进度回调
        验证回调函数被正确调用
        """
        test_file = tmp_path / "test_progress.txt"
        test_file.write_text("测试进度回调的内容。" * 30, encoding="utf-8")

        doc = Document(
            filename="test_progress.txt",
            file_path=str(test_file),
            file_size=test_file.stat().st_size,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        progress_calls = []

        def callback(current, total, stage):
            progress_calls.append((current, total, stage))

        processor.process_document(doc, db, progress_callback=callback)

        # 验证回调被调用
        assert len(progress_calls) > 0, "进度回调未被调用"
        # 验证最后一个回调是完成状态
        assert progress_calls[-1][2] == "完成"
        assert progress_calls[-1][0] == 100

        # 清理
        processor.delete_document_vectors(doc.id, db)
        db.execute(text(f"DELETE FROM documents WHERE id = {doc.id}"))
        db.commit()
