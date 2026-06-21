"""
向量库一致性检查
检查数据库记录与向量库数据的一致性，并清理孤儿向量
"""

import logging
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Document
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class VectorConsistencyChecker:
    """向量库一致性检查器"""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    def check_consistency(self, db: Session) -> Dict:#检查数据库与向量库的一致性
        """
        检查数据库与向量库的一致性
        
        Returns:
            检查结果字典
        """
        if not self.vector_store._available:
            return {
                "status": "error",
                "message": "向量库不可用"
            }
        
        try:
            # 1. 获取数据库中所有已完成的文档ID
            db_documents = db.query(Document.id).filter(
                Document.status == "completed"
            ).all()
            db_doc_ids = set(doc.id for doc in db_documents)
            
            # 2. 获取向量库中的所有文档ID
            total_entities = self.vector_store.child_collection.num_entities
            if total_entities == 0:
                vector_doc_ids = set()
            else:
                vector_results = self.vector_store.child_collection.query(
                    expr="document_id > 0",
                    output_fields=["document_id"],
                    limit=min(total_entities, 16384)
                )
                vector_doc_ids = set(r.get("document_id") for r in vector_results)
            
            # 3. 计算不一致的部分
            orphan_vectors = vector_doc_ids - db_doc_ids  # 向量库中有但数据库中没有
            missing_vectors = db_doc_ids - vector_doc_ids  # 数据库中有但向量库中没有
            
            result = {#检查结果字典
                "status": "success",
                "total_entities": total_entities,
                "db_document_count": len(db_doc_ids),
                "vector_document_count": len(vector_doc_ids),
                "orphan_documents": list(orphan_vectors),
                "missing_documents": list(missing_vectors),
                "is_consistent": len(orphan_vectors) == 0 and len(missing_vectors) == 0
            }
            
            if not result["is_consistent"]:
                logger.warning(f"向量库不一致: 孤儿文档={orphan_vectors}, 缺失文档={missing_vectors}")
            else:
                logger.info("向量库一致性检查通过")
            
            return result
            
        except Exception as e:
            logger.error(f"一致性检查失败: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def clean_orphan_vectors(self, db: Session = None) -> int:
        """
        清理孤儿向量
        
        分两步：
        1. 删除 document_id <= 0 的无效向量
        2. 删除 document_id 在 Milvus 中存在但 MySQL 中不存在的向量
        
        Returns:
            清理的向量数量
        """
        if not self.vector_store._available:
            logger.warning("向量库不可用，无法清理孤儿向量")
            return 0
        
        try:
            deleted_count = self.vector_store.delete_orphan_vectors()
            
            # 清理 MySQL 中不存在的 document_id
            if db:
                consistency = self.check_consistency(db)
                orphans = consistency.get("orphan_documents", [])
                if orphans:
                    for doc_id in orphans:
                        self.vector_store.delete_by_document_id(doc_id)
                        logger.info(f"删除孤儿文档向量: document_id={doc_id}")
                    deleted_count += len(orphans)
            
            logger.info(f"孤儿向量清理完成，删除了 {deleted_count} 条")
            return deleted_count
        except Exception as e:
            logger.error(f"清理孤儿向量失败: {str(e)}")
            return 0
    
    def rebuild_vectors_for_document(self, document_id: int, db: Session) -> bool:
        """
        重建指定文档的向量数据
        
        Args:
            document_id: 文档ID
            db: 数据库会话
            
        Returns:
            是否重建成功
        """
        try:
            # 1. 获取文档信息
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                logger.warning(f"文档不存在: {document_id}")
                return False
            
            if document.status != "completed":
                logger.warning(f"文档未完成: {document_id}, 状态: {document.status}")
                return False
            
            # 2. 删除现有向量 + MySQL 父块记录（避免重建时产生重复数据）
            self.vector_store.delete_by_document_id(document_id)
            from app.models import ParentChunk
            deleted_mysql = db.query(ParentChunk).filter(
                ParentChunk.document_id == document_id
            ).delete()
            db.commit()
            if deleted_mysql:
                logger.info(f"已删除文档 {document_id} 的 {deleted_mysql} 条 MySQL 父块记录")
            
            # 3. 重新处理文档
            from app.services.document_processor import DocumentProcessor
            processor = DocumentProcessor()
            processor.process_document(document, db)
            
            logger.info(f"文档向量重建完成: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"重建文档向量失败: {document_id}, 错误: {str(e)}")
            return False
