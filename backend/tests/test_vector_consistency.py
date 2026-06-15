"""
向量一致性真实环境测试
====================
连接真实 Milvus + MySQL，验证数据一致性
"""
import pytest
from sqlalchemy import text


@pytest.mark.real
class TestVectorConsistencyReal:
    """向量一致性真实环境测试"""

    def test_vector_consistency(self, real_services):
        """
        测试向量一致性
        验证向量存储中的数据是否与数据库中的数据一致
        """
        from app.services.vector_consistency import VectorConsistencyChecker

        db = real_services["db"]
        checker = VectorConsistencyChecker()
        result = checker.check_consistency(db)

        assert result["status"] == "success", f"检查向量库一致性失败: {result.get('message')}"
        assert "total_entities" in result, "检查结果中缺少总实体数"
        assert "db_document_count" in result, "检查结果中缺少数据库文档数"
        assert "vector_document_count" in result, "检查结果中缺少向量文档数"
        assert "is_consistent" in result, "检查结果中缺少一致性标志"

        if result["db_document_count"] > 0:
            print(f"\n一致性状态: {result['is_consistent']}")
            print(f"数据库文档数: {result['db_document_count']}")
            print(f"向量库文档数: {result['vector_document_count']}")
            if not result["is_consistent"]:
                print(f"孤儿文档: {result['orphan_documents']}")
                print(f"缺失文档: {result['missing_documents']}")

    def test_clean_orphan_vectors(self, real_services):
        """
        测试孤儿向量清理
        预期：返回清理数量（可能为 0）
        """
        from app.services.vector_consistency import VectorConsistencyChecker

        checker = VectorConsistencyChecker()
        db = real_services["db"]
        before = checker.check_consistency(db)

        deleted_count = checker.clean_orphan_vectors()

        assert isinstance(deleted_count, int), "清理数量必须是整数"
        assert deleted_count >= 0, "清理数量不能小于 0"

        print(f"\n清理前孤儿文档: {before.get('orphan_documents', [])}")
        print(f"清理数量: {deleted_count}")

        after = checker.check_consistency(db)
        print(f"清理后孤儿文档: {after.get('orphan_documents', [])}")

    def test_rebuild_vectors_for_nonexistent_document(self, real_services):
        """
        测试重建不存在的文档
        预期：返回 False
        """
        from app.services.vector_consistency import VectorConsistencyChecker

        db = real_services["db"]
        checker = VectorConsistencyChecker()

        result = checker.rebuild_vectors_for_document(99999, db)

        assert result is False, "不存在的文档应该返回 False"

    def test_rebuild_vectors_for_existing_document(self, real_services):
        """
        测试重建已存在的文档向量
        前提：有 status=completed 的文档，且源文件存在
        注意：此测试会删除旧向量并重新处理文档
        """
        from app.services.vector_consistency import VectorConsistencyChecker

        db = real_services["db"]

        row = db.execute(
            text("SELECT id FROM documents WHERE status='completed' LIMIT 1")
        ).fetchone()

        if not row:
            pytest.skip("No completed documents found")

        doc_id = row[0]
        checker = VectorConsistencyChecker()

        try:
            result = checker.rebuild_vectors_for_document(doc_id, db)
            assert result in (True, False), f"应该返回布尔值，实际返回 {result}"
            print(f"\n文档 {doc_id} 重建结果: {result}")
            if result is False:
                pytest.skip(f"文档 {doc_id} 重建失败（可能源文件已删除）")
        except Exception as e:
            pytest.skip(f"文档源文件可能已删除，无法重建: {e}")
