"""
向量化服务
===========
调用通义千问 Embedding API 将文本转换为向量
支持 Redis 缓存，相同文本不重复调用 API
支持指数退避重试机制
"""

from typing import List
import hashlib
import time
import logging
import dashscope
from dashscope import TextEmbedding
from app.core.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务"""

    def __init__(self):
        """初始化向量化服务"""
        import os
        
        # 只从系统环境变量读取 API Key，不经过 .env 文件
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        
        if api_key:
            logger.info(f"DashScope API Key 已加载 (长度: {len(api_key)})")
        else:
            logger.warning("DashScope API Key 未配置，请设置系统环境变量 DASHSCOPE_API_KEY")
        
        dashscope.api_key = api_key
        # 不再固化模型名称，改为动态获取
        self.cache_ttl = 86400 * 7  # 缓存 7 天
        self.max_retries = 3
        self.base_delay = 1  # 基础延迟 1 秒

    def _get_current_model_name(self, db=None) -> str:
        """
        获取当前使用的 Embedding 模型名称
        
        优先从数据库读取激活的配置，如果没有则使用环境变量中的默认值
        
        Args:
            db: 数据库会话（可选）
            
        Returns:
            模型名称
        """
        if db:
            try:
                from app.models import ModelConfig
                active_embedding = db.query(ModelConfig).filter(
                    ModelConfig.model_type == "embedding",
                    ModelConfig.is_active == True
                ).first()
                
                if active_embedding:
                    return active_embedding.model_name
            except Exception as e:
                logger.warning(f"读取数据库 Embedding 模型配置失败：{e}")
        
        # 如果数据库没有配置，使用环境变量中的默认值
        from app.core.config import settings
        return settings.EMBEDDING_MODEL

    def _get_cache_key(self, text: str, model_name: str) -> str:
        """
        生成文本的缓存键
        
        Args:
            text: 原始文本
            model_name: 模型名称
            
        Returns:
            缓存键（MD5 哈希）
        """
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        return f"embedding:{model_name}:{text_hash}"

    def _call_with_retry(self, texts, model_name, is_batch=False):
        """
        带指数退避重试的 API 调用
        
        Args:
            texts: 文本或文本列表
            model_name: 模型名称
            is_batch: 是否批量调用
            
        Returns:
            API 响应
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = TextEmbedding.call(
                    model=model_name,
                    input=texts,
                )

                if response.status_code == 200:
                    return response
                
                # API 返回错误，记录并重试
                error_msg = response.message
                logger.warning(f"向量化 API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                last_error = error_msg
                
            except Exception as e:
                logger.warning(f"向量化 API 调用异常 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                last_error = str(e)
            
            # 指数退避等待
            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2 ** attempt)
                logger.info(f"等待 {delay} 秒后重试...")
                time.sleep(delay)
        
        raise RuntimeError(f"向量化失败，已重试 {self.max_retries} 次: {last_error}")

    def embed(self, text: str, db=None) -> List[float]:
        """
        将单个文本转换为向量（带缓存和重试）
        
        Args:
            text: 要向量化的文本
            db: 数据库会话（可选）
            
        Returns:
            向量列表
        """
        if not text or not text.strip():
            return []

        # 获取当前模型名称
        model_name = self._get_current_model_name(db)

        # 尝试从缓存获取
        cache_key = self._get_cache_key(text, model_name)
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        # 调用 API（带重试）
        response = self._call_with_retry(text, model_name=model_name, is_batch=False)

        embedding = response.output["embeddings"][0]["embedding"]
        # 写入缓存
        cache_service.set(cache_key, embedding, self.cache_ttl)
        return embedding

    def embed_batch(self, texts: List[str], batch_size: int = 10, db=None) -> List[List[float]]:
        """
        批量将文本转换为向量（带缓存优化和重试）
        
        Args:
            texts: 要向量化的文本列表
            batch_size: 每批处理的文本数量
            db: 数据库会话（可选）
            
        Returns:
            向量列表的列表
        """
        # 获取当前模型名称
        model_name = self._get_current_model_name(db)
        
        # 过滤空文本并记录原始索引
        valid_texts = []
        original_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                original_indices.append(i)
            else:
                logger.warning(f"跳过空文本块 (索引 {i})")

        if not valid_texts:
            logger.warning("所有文本块均为空，返回空向量列表")
            return [[] for _ in texts]

        all_embeddings = []

        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i : i + batch_size]
            
            # 1. 检查缓存
            cached_embeddings = []
            uncached_texts = []
            uncached_indices = []
            
            for idx, text in enumerate(batch):
                cache_key = self._get_cache_key(text, model_name)
                cached = cache_service.get(cache_key)
                if cached:
                    cached_embeddings.append((idx, cached))
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(idx)
            
            # 2. 调用 API 获取未缓存的文本（带重试）
            new_embeddings = []
            if uncached_texts:
                response = self._call_with_retry(uncached_texts, model_name=model_name, is_batch=True)

                # 验证 API 返回的向量数量
                api_embeddings = response.output.get("embeddings", [])
                if len(api_embeddings) != len(uncached_texts):
                    raise ValueError(
                        f"API 返回向量数量不匹配: 请求 {len(uncached_texts)} 个，返回 {len(api_embeddings)} 个"
                    )

                for item in api_embeddings:
                    new_embeddings.append(item["embedding"])
                
                # 写入缓存
                for text, embedding in zip(uncached_texts, new_embeddings):
                    cache_key = self._get_cache_key(text, model_name)
                    cache_service.set(cache_key, embedding, self.cache_ttl)
            
            # 3. 合并缓存和新结果（保持原始顺序）
            batch_result = [None] * len(batch)
            for idx, emb in cached_embeddings:
                batch_result[idx] = emb
            for idx, emb in zip(uncached_indices, new_embeddings):
                batch_result[idx] = emb
            
            # 验证本批结果完整性
            if None in batch_result:
                missing = batch_result.count(None)
                raise ValueError(f"批次向量化结果不完整: {missing}/{len(batch)} 个向量缺失")
            
            all_embeddings.extend(batch_result)

        # 最终验证
        if len(all_embeddings) != len(valid_texts):
            raise ValueError(
                f"向量化结果数量不匹配: 输入 {len(valid_texts)} 个文本，返回 {len(all_embeddings)} 个向量"
            )

        # 重建完整结果（包含空文本的占位）
        full_result = [[] for _ in texts]
        for valid_idx, original_idx in enumerate(original_indices):
            full_result[original_idx] = all_embeddings[valid_idx]

        return full_result
