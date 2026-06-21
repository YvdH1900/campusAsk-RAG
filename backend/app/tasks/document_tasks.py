"""
文档处理 Celery 任务（重构版）
==============================
异步处理文档：预处理 → 解析 → 清洗 → 分块 → 向量化 → 入库

新特性：
- 上传即返回，不占主线程
- 自动重试、失败告警、状态追踪
- 大文件拆分独立处理
- 低质量内容自动拦截报告
"""

import gc
import logging
import os
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
    time_limit=3600,  # 硬超时：60 分钟（大文件/OCR 需要更长时间）
    soft_time_limit=3300,  # 软超时：55 分钟
)
def process_document_task(self, document_id: int, is_large_file: bool = False, split_files: list = None):
    """
    异步处理文档任务

    Args:
        document_id: 文档ID
        is_large_file: 是否为大文件（需要拆分），拆分在任务内部异步执行
        split_files: 已拆分的文件路径列表（兼容旧调用，新调用应传 is_large_file=True）
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"文档不存在：document_id={document_id}")
            return {"status": "failed", "error": "文档不存在"}

        # 检查文档状态，已处理过的跳过
        if document.status in ("failed", "completed"):
            logger.warning(
                f"文档状态为 {document.status}，跳过处理："
                f"document_id={document_id}, filename={document.filename}"
            )
            return {"status": "skipped", "reason": f"document already {document.status}"}

        # ---- 大文件拆分（在 Celery 任务内异步执行，不阻塞上传接口） ----
        if is_large_file and not split_files and document.file_path and os.path.exists(document.file_path):
            from app.api.documents import split_large_file
            try:
                split_files = split_large_file(document.file_path, document.filename)
                if split_files:
                    logger.info(
                        f"Celery 任务内大文件拆分: {document.filename} "
                        f"({document.file_size/1024/1024:.1f}MB) -> {len(split_files)} 个子文件"
                    )
                else:
                    logger.info(f"大文件无需拆分: {document.filename}")
            except Exception as split_err:
                logger.error(f"大文件拆分失败: {split_err}", exc_info=True)
                # 拆分失败不阻塞，继续按原文件处理
                split_files = None

        def progress_callback(current, total, stage):
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": current,
                    "total": total,
                    "stage": stage,
                    "document_id": document_id,
                },
            )

        processor = DocumentProcessor()

        if split_files:
            logger.info(
                f"大文件拆分处理: {document.filename}, "
                f"{len(split_files)} 个子文件"
            )
            processor.process_split_document(
                document, split_files, db,
                progress_callback=progress_callback,
            )
        else:
            processor.process_document(
                document, db,
                progress_callback=progress_callback,
            )

        logger.info(
            f"文档处理成功: document_id={document_id}, "
            f"filename={document.filename}"
        )
        return {
            "status": "success",
            "document_id": document_id,
            "filename": document.filename,
        }

    except Exception as exc:
        logger.error(
            f"文档处理失败：document_id={document_id}, "
            f"error={str(exc)}"
        )

        if self.request.retries >= self.max_retries:
            logger.error(
                f"文档处理已达最大重试次数 ({self.max_retries})，"
                f"不再重试：document_id={document_id}"
            )
            try:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = "failed"
                    db.commit()
            except Exception:
                pass
            return {
                "status": "failed",
                "error": str(exc),
                "retries": self.request.retries,
                "max_retries": self.max_retries,
            }

        logger.info(
            f"文档处理失败，准备重试 "
            f"({self.request.retries + 1}/{self.max_retries}): "
            f"document_id={document_id}"
        )
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
        processor = DocumentProcessor()
        processor.delete_document_vectors(document_id)
        logger.info(f"文档向量删除成功: document_id={document_id}")
        return {"status": "success", "document_id": document_id}
    except Exception as exc:
        logger.error(
            f"文档向量删除失败: document_id={document_id}, "
            f"error={str(exc)}"
        )
        raise exc