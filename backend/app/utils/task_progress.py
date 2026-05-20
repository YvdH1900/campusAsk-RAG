"""
任务进度追踪模块
================
用于追踪后台任务的执行进度
"""

import threading
from datetime import datetime
from typing import Dict, Optional
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"  # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败


class TaskProgress:
    """任务进度"""
    
    def __init__(self, task_id: str, task_type: str, total: int = 100):
        self.task_id = task_id
        self.task_type = task_type  # 如：rebuild_vector_store
        self.status = TaskStatus.PENDING
        self.current = 0
        self.total = total
        self.stage = "初始化"  # 当前阶段描述
        self.message = ""  # 详细信息
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
    
    def update(self, current: int, stage: str, message: str = ""):
        """更新进度"""
        self.current = current
        self.stage = stage
        self.message = message
        self.status = TaskStatus.PROCESSING
        self.updated_at = datetime.now()
    
    def complete(self, message: str = ""):
        """标记任务完成"""
        self.current = self.total
        self.status = TaskStatus.COMPLETED
        self.stage = "完成"
        self.message = message
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
    
    def fail(self, error_message: str):
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.stage = "失败"
        self.error_message = error_message
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "current": self.current,
            "total": self.total,
            "progress": round((self.current / self.total) * 100, 2) if self.total > 0 else 0,
            "stage": self.stage,
            "message": self.message,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ProgressStore:
    """进度存储（线程安全）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tasks: Dict[str, TaskProgress] = {}
        self._lock = threading.Lock()
    
    def add_task(self, task: TaskProgress):
        """添加任务"""
        with self._lock:
            self._tasks[task.task_id] = task
    
    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务进度"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, current: int, stage: str, message: str = ""):
        """更新任务进度"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.update(current, stage, message)
    
    def complete_task(self, task_id: str, message: str = ""):
        """完成任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.complete(message)
    
    def fail_task(self, task_id: str, error_message: str):
        """任务失败"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.fail(error_message)
    
    def get_all_tasks(self) -> list:
        """获取所有任务"""
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        from datetime import timedelta
        now = datetime.now()
        with self._lock:
            to_remove = [
                task_id for task_id, task in self._tasks.items()
                if task.completed_at and (now - task.completed_at) > timedelta(hours=max_age_hours)
            ]
            for task_id in to_remove:
                del self._tasks[task_id]


# 全局进度存储实例
progress_store = ProgressStore()


def generate_task_id(task_type: str) -> str:
    """生成任务 ID"""
    import uuid
    return f"{task_type}_{uuid.uuid4().hex[:8]}"
