"""
结构化日志配置
===============
企业级日志系统，支持：
- JSON格式输出（便于ELK/Loki收集）
- 日志级别动态调整
- 请求追踪ID自动关联
- 敏感信息脱敏
- 文件轮转和归档
- 控制台彩色输出（开发环境）
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict
import os


class ColoredFormatter(logging.Formatter):
    """
    彩色日志格式化器
    
    开发环境使用，提供可读性更好的控制台输出
    不同日志级别使用不同颜色：
    - DEBUG: 蓝色
    - INFO: 绿色  
    - WARNING: 黄色
    - ERROR: 红色
    - CRITICAL: 红色加粗
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[1;31m' # 红色加粗
    }
    RESET = '\033[0m'
    
    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record):
        if self.use_colors:
            levelname = f"{self.COLORS.get(record.levelname, '')}{record.levelname}{self.RESET}"
            record.levelname = levelname
        
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """
    JSON格式化器
    
    生产环境使用，输出结构化JSON日志
    便于ELK Stack、Loki等日志系统收集和分析
    
    输出格式：
    {
        "timestamp": "2024-01-01T12:00:00.000Z",
        "level": "INFO",
        "logger": "app.api.auth",
        "message": "用户登录成功",
        "request_id": "req-abc123def456",
        "extra": {...}
    }
    """
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": self._sanitize_message(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if hasattr(record, 'request_id') and record.request_id:
            log_entry["request_id"] = record.request_id
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in (
                'name', 'msg', 'args', 'created', 'filename',
                'funcName', 'levelname', 'levelno', 'module',
                'exc_info', 'exc_text', 'stack_info', 'lineno',
                'message', 'request_id'
            ):
                extra[key] = self._sanitize_value(value)
        
        if extra:
            log_entry["extra"] = extra
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return __import__('json').dumps(log_entry, ensure_ascii=False)
    
    def _sanitize_message(self, message: str) -> str:
        """
        清理敏感信息
        
        Args:
            message: 原始消息
            
        Returns:
            清理后的消息
        """
        sensitive_patterns = [
            (r'password\s*[:=]\s*\S+', 'password=[REDACTED]'),
            (r'token\s*[:=]\s*\S+', 'token=[REDACTED]'),
            (r'api_key\s*[:=]\s*\S+', 'api_key=[REDACTED]'),
            (r'sk-[a-zA-Z0-9]{20,}', 'sk-[REDACTED]'),
        ]
        
        import re
        for pattern, replacement in sensitive_patterns:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        
        return message
    
    def _sanitize_value(self, value: Any) -> Any:
        """
        递归清理敏感值
        
        Args:
            value: 待清理的值
                
        Returns:
            清理后的值
        """
        if isinstance(value, str):
            return self._sanitize_message(value)
        elif isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        else:
            return value


def setup_logging(
    level: str = "INFO",
    log_file: str = None,
    json_format: bool = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5
):
    """
    配置全局日志系统
    
    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        log_file: 日志文件路径（可选）
        json_format: 是否使用JSON格式（None表示自动判断：生产环境用JSON）
        max_bytes: 单个日志文件最大大小（字节）
        backup_count: 保留的日志文件数量
    """
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    root_logger.handlers.clear()
    
    is_production = os.getenv('ENVIRONMENT', 'development') == 'production'
    use_json = json_format if json_format is not None else is_production
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if sys.platform == 'win32':
        console_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    
    if use_json:
        console_formatter = JsonFormatter()
    else:
        console_formatter = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    if log_file:
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        file_formatter = JsonFormatter() if use_json else logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('uvicorn.access').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"✅ 日志系统初始化完成 | 级别={level.upper()} | 格式={'JSON' if use_json else '彩色文本'}")
    if log_file:
        logger.info(f"📝 日志文件: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    获取Logger实例
    
    Args:
        name: Logger名称（通常使用__name__）
        
    Returns:
        配置好的Logger实例
    """
    return logging.getLogger(name)
