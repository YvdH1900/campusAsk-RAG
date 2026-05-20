"""
文档处理服务（企业级）
====================
整合文档解析、分块、向量化和存储的完整流程
支持：
- 事务回滚、缓存清理、错误重试
- 进度追踪
- 分块质量评估
- 多语言支持
"""

import logging
from typing import Optional, Callable
from sqlalchemy.orm import Session
from app.models import Document
from app.services.document_parser import DocumentParser
from app.services.text_splitter import TextSplitter
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        """初始化文档处理器"""
        self.parser = DocumentParser()
        self.splitter = TextSplitter()
        self.embedder = EmbeddingService()
        self.vector_store = None  # 延迟初始化，需要 db 时再创建

    def _get_vector_store(self, db: Session):
        """获取或创建 VectorStore 实例（带 db）"""
        if self.vector_store is None:
            self.vector_store = VectorStore(db=db)
        return self.vector_store

    def process_document(
        self,
        document: Document,
        db: Session,
        progress_callback: Optional[Callable] = None,
    ):
        """
        处理文档：解析 -> 分块 -> 向量化 -> 存储
        
        使用事务保证数据一致性：
        - 向量入库失败时回滚文档状态
        - 处理成功后清除相关缓存
        
        Args:
            document: 文档对象
            db: 数据库会话
            progress_callback: 进度回调函数 callback(current, total, stage)
        """
        def report_progress(current, total, stage):
            if progress_callback:
                progress_callback(current, total, stage)
            logger.info(f"进度: {stage} - {current}/{total}")

        try:
            # 仅在初始状态时更新为处理中（避免重试时覆盖失败状态）
            if document.status in ("pending", "approved"):
                document.status = "processing"
                db.commit()

            # 1. 解析文档
            report_progress(0, 100, "解析文档")
            logger.info(f"开始解析文档: {document.filename}")
            text = self.parser.parse(document.file_path)

            if not text.strip():
                raise ValueError("文档内容为空")

            # 检测语言
            lang = self.parser.detect_language(text)
            logger.info(f"文档语言: {lang}")

            report_progress(20, 100, "分块处理")

            # 2. 文本分块（父子分块）
            logger.info(f"开始分块文档: {document.filename}")
            chunks = self.splitter.split(text)

            if not chunks:
                raise ValueError("文档分块后为空")

            # 分块质量评估
            quality = self.splitter.evaluate_quality(chunks)
            logger.info(f"分块质量: {quality}")

            # 提取子块内容用于向量化
            child_contents = [chunk["child_content"] for chunk in chunks]
            parent_count = len(set(c["parent_id"] for c in chunks))
            logger.info(f"文档 {document.filename} 分为 {len(chunks)} 个子块，对应 {parent_count} 个父块")

            report_progress(40, 100, "向量化")

            # 3. 向量化（子块）
            logger.info(f"开始向量化文档: {document.filename}")
            total_chunks = len(child_contents)
            
            # 直接调用 embed_batch，由 embedding_service 内部统一处理分批
            all_embeddings = self.embedder.embed_batch(child_contents, db=db)

            report_progress(80, 100, "存储向量")

            # 4. 存储到向量数据库（关键步骤，失败需要回滚）
            logger.info(f"开始存储向量: {document.filename}")
            vector_store = self._get_vector_store(db)
            try:
                vector_store.insert(document.id, chunks, all_embeddings)
            except Exception as e:
                # 向量入库失败，回滚文档状态并清理可能已插入的向量
                logger.error(f"向量入库失败，回滚文档状态: {document.filename}, 错误: {str(e)}")
                
                # 尝试清理可能已插入的孤儿向量
                try:
                    vector_store.delete_by_document_id(document.id)
                    logger.info(f"已清理文档 {document.id} 的残留向量")
                except Exception as cleanup_error:
                    logger.warning(f"清理残留向量失败: {str(cleanup_error)}")
                
                document.status = "failed"
                db.commit()
                raise

            # 5. 更新状态为完成
            document.status = "completed"
            db.commit()

            # 6. 清除搜索缓存（文档更新后缓存失效）
            cache_service.clear_pattern("search:*")
            cache_service.clear_pattern(f"document:{document.id}:*")

            report_progress(100, 100, "完成")
            logger.info(f"文档处理完成: {document.filename}, 共 {len(chunks)} 个子块")

        except Exception as e:
            # 更新状态为失败
            try:
                document.status = "failed"
                db.commit()
            except Exception as db_error:
                logger.error(f"更新文档失败状态时出错: {str(db_error)}")
                db.rollback()
            
            logger.error(f"文档处理失败: {document.filename}, 错误: {str(e)}")
            raise

    def delete_document_vectors(self, document_id: int, db=None):
        """
        删除文档的向量数据
        
        Args:
            document_id: 文档ID
            db: 数据库会话（可选，用于动态读取向量维度）
        """
        try:
            vector_store = self._get_vector_store(db) if db else VectorStore()
            vector_store.delete_by_document_id(document_id)
            # 清除相关缓存
            cache_service.clear_pattern(f"document:{document_id}:*")
            logger.info(f"已删除文档向量: document_id={document_id}")
        except Exception as e:
            logger.error(f"删除文档向量失败: document_id={document_id}, 错误: {str(e)}")
