"""
文档处理 Celery 任务
====================
异步处理文档：解析 -> 分块 -> 向量化 -> 入库
支持自动重试、失败告警、状态追踪、进度更新
"""

import gc
import logging
import time
from celery import shared_task
from app.core.database import SessionLocal
from app.models import Document
from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="app.tasks.document_tasks.process_document",
    max_retries=3,
    default_retry_delay=60,
    time_limit=1800,  # 硬超时：30 分钟
    soft_time_limit=1500,  # 软超时：25 分钟
)
def process_document_task(self, document_id: int, split_files: list = None):
    """
    异步处理文档任务
    
    Args:
        document_id: 文档ID
        split_files: 拆分后的文件路径列表（大文件拆分时传入，小文件为 None）
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"文档不存在：document_id={document_id}")
            return {"status": "failed", "error": "文档不存在"}
        
        # 检查文档状态，如果已经是失败/已拆分状态，不再重复处理
        if document.status in ("failed", "split"):
            logger.warning(f"文档状态为 {document.status}，跳过处理：document_id={document_id}, filename={document.filename}")
            return {"status": "skipped", "reason": f"document already {document.status}"}

        # 进度回调函数
        def progress_callback(current, total, stage):
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": current,
                    "total": total,
                    "stage": stage,
                    "document_id": document_id,
                }
            )

        processor = DocumentProcessor()
        
        if split_files:
            # 大文件拆分处理：逐个处理拆分文件，所有向量共享同一个 document_id
            logger.info(f"大文件拆分处理: {document.filename}, {len(split_files)} 个子文件")
            processor.process_split_document(document, split_files, db, progress_callback=progress_callback)
        else:
            # 普通文件处理
            processor.process_document(document, db, progress_callback=progress_callback)

        logger.info(f"文档处理成功: document_id={document_id}, filename={document.filename}")
        return {
            "status": "success",
            "document_id": document_id,
            "filename": document.filename,
        }

    except Exception as exc:
        logger.error(f"文档处理失败：document_id={document_id}, error={str(exc)}")
        
        # 检查是否已达到最大重试次数
        if self.request.retries >= self.max_retries:
            logger.error(f"文档处理已达最大重试次数 ({self.max_retries})，不再重试：document_id={document_id}")
            
            # 更新文档状态为失败
            try:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = "failed"
                    db.commit()
            except Exception:
                pass
            
            # 返回失败结果，不再重试
            return {
                "status": "failed",
                "error": str(exc),
                "retries": self.request.retries,
                "max_retries": self.max_retries,
            }
        
        # 否则继续重试
        logger.info(f"文档处理失败，准备重试 ({self.request.retries + 1}/{self.max_retries}): document_id={document_id}")
        raise self.retry(exc=exc)
    
    finally:
        db.close()


@shared_task(
    name="app.tasks.document_tasks.delete_document_vectors",
)
def delete_document_vectors_task(document_id: int):
    """
    删除文档向量任务
    
    Args:
        document_id: 文档ID
    """
    try:
        from app.services.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        processor.delete_document_vectors(document_id)
        logger.info(f"文档向量删除成功: document_id={document_id}")
        return {"status": "success", "document_id": document_id}
    except Exception as exc:
        logger.error(f"文档向量删除失败: document_id={document_id}, error={str(exc)}")
        raise exc
