"""
Redis 缓存服务（支持内存降级）
==============
提供缓存读写、TTL 管理、缓存穿透防护
当 Redis 不可用时自动降级到内存缓存
"""

import json
import time
import redis
import logging
from typing import Optional, Any, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存（Redis 不可用时的降级方案）"""

    def __init__(self, max_size: int = 10000):
        self._store: Dict[str, dict] = {}
        self._max_size = max_size

    def _cleanup_if_needed(self):
        """清理过期条目，如果超过最大大小则清理最旧的"""
        now = time.time()
        expired_keys = [
            k for k, v in self._store.items()
            if v["expire_at"] is not None and now >= v["expire_at"]
        ]
        for k in expired_keys:
            del self._store[k]

        if len(self._store) > self._max_size:
            sorted_items = sorted(
                self._store.items(),
                key=lambda x: x[1]["expire_at"] or 0,
            )
            for k, _ in sorted_items[: len(self._store) - self._max_size]:
                del self._store[k]

    def get(self, key: str) -> Optional[str]:
        if key in self._store:
            item = self._store[key]
            if item["expire_at"] is None or time.time() < item["expire_at"]:
                return item["value"]
            else:
                del self._store[key]
        return None

    def setex(self, key: str, ttl: int, value: str):
        self._cleanup_if_needed()
        self._store[key] = {
            "value": value,
            "expire_at": time.time() + ttl,
        }

    def delete(self, key: str):
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        if key in self._store:
            item = self._store[key]
            if item["expire_at"] is None or time.time() < item["expire_at"]:
                return True
            else:
                del self._store[key]
        return False

    def keys(self, pattern: str) -> list:
        import fnmatch
        return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]


class CacheService:
    """Redis 缓存服务（支持内存降级）"""

    def __init__(self):
        """初始化缓存连接"""
        self._redis_available = False
        self._memory_cache = MemoryCache()
        self._client = None

        try:
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=2,
            )
            client.ping()
            self._client = client
            self._redis_available = True
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 不可用，使用内存缓存: {str(e)}")
            self._redis_available = False

    @property
    def client(self):
        if self._redis_available:
            return self._client
        return self._memory_cache

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在则返回 None
        """
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"缓存读取失败: key={key}, error={str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 则使用默认 TTL
            
        Returns:
            是否设置成功
        """
        try:
            ttl = ttl or settings.CACHE_TTL
            serialized = json.dumps(value, ensure_ascii=False)
            self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"缓存写入失败: key={key}, error={str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"缓存删除失败: key={key}, error={str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"缓存检查失败: key={key}, error={str(e)}")
            return False

    def get_or_set(self, key: str, default_func, ttl: Optional[int] = None) -> Any:
        """
        获取缓存，如果不存在则调用函数生成并缓存
        
        Args:
            key: 缓存键
            default_func: 生成默认值的函数
            ttl: 过期时间（秒）
            
        Returns:
            缓存值或新生成的值
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = default_func()
        if value is not None:
            self.set(key, value, ttl)
        return value

    def clear_pattern(self, pattern: str) -> int:
        """
        清除匹配模式的缓存
        
        Args:
            pattern: 键模式，如 "search:*"
            
        Returns:
            清除的键数量
        """
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"批量清除缓存失败: pattern={pattern}, error={str(e)}")
            return 0


cache_service = CacheService()
