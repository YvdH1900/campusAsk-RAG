"""
Celery 异步任务配置
===================
使用 RabbitMQ 作为消息队列，Redis 作为结果后端
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "campus_ask",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.document_tasks",
    ],
)

celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务结果设置
    result_expires=settings.CELERY_RESULT_EXPIRES,
    
    # 任务执行设置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    
    # 任务重试设置
    task_default_retry_delay=settings.CELERY_TASK_RETRY_DELAY,
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
    
    # 速率限制
    task_annotations={
        "app.tasks.document_tasks.process_document": {
            "rate_limit": "10/m",
        },
    },
)
