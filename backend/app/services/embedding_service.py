"""
向量化服务
===========
调用通义千问 Embedding API 将文本转换为向量
支持 Redis 缓存，相同文本不重复调用 API
支持指数退避重试机制
支持 text-embedding-v3/v4 的 dimension 参数
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

        api_key = os.environ.get("DASHSCOPE_API_KEY", "")

        if api_key:
            logger.info(f"DashScope API Key 已加载 (长度: {len(api_key)})")
        else:
            logger.warning("DashScope API Key 未配置，请设置系统环境变量 DASHSCOPE_API_KEY")

        dashscope.api_key = api_key
        self.cache_ttl = 86400 * 7
        self.max_retries = 3
        self.base_delay = 1

    def _get_current_model_name(self, db=None) -> str:
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

        from app.core.config import settings
        return settings.EMBEDDING_MODEL

    def _get_current_dimension(self, db=None) -> int | None:
        if db:
            try:
                from app.models import ModelConfig
                active_embedding = db.query(ModelConfig).filter(
                    ModelConfig.model_type == "embedding",
                    ModelConfig.is_active == True
                ).first()

                if active_embedding and active_embedding.dimension:
                    return active_embedding.dimension
            except Exception as e:
                logger.warning(f"读取数据库 Embedding 维度配置失败：{e}")

        import os
        env_dimension = os.environ.get("EMBEDDING_DIMENSION")
        if env_dimension:
            try:
                return int(env_dimension)
            except ValueError:
                pass

        # Check config.py
        from app.core.config import settings
        if hasattr(settings, "EMBEDDING_DIMENSION") and settings.EMBEDDING_DIMENSION:
            return settings.EMBEDDING_DIMENSION

        return None

    def _get_cache_key(self, text: str, model_name: str, dimension: int | None) -> str:
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        dim_str = str(dimension) if dimension else "default"
        return f"embedding:{model_name}:{dim_str}:{text_hash}"

    def _call_with_retry(self, texts, model_name, dimension=None, is_batch=False):
        last_error = None
        if dimension is not None:
            logger.info(f"调用 Embedding API: model={model_name}, dimension={dimension}")

        for attempt in range(self.max_retries):
            try:
                kwargs = {"model": model_name, "input": texts}
                if dimension is not None:
                    kwargs["dimension"] = dimension

                response = TextEmbedding.call(**kwargs)

                if response.status_code == 200:
                    return response

                error_msg = response.message
                logger.warning(f"向量化 API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                last_error = error_msg

            except Exception as e:
                logger.warning(f"向量化 API 调用异常 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                last_error = str(e)

            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2 ** attempt)
                logger.info(f"等待 {delay} 秒后重试...")
                time.sleep(delay)

        raise RuntimeError(f"向量化失败，已重试 {self.max_retries} 次: {last_error}")

    def embed(self, text: str, db=None, model_name_override: str = None,
              dimension_override: int = None) -> List[float]:
        if not text or not text.strip():
            return []

        model_name = model_name_override or self._get_current_model_name(db)
        dimension = dimension_override if dimension_override is not None else self._get_current_dimension(db)

        cache_key = self._get_cache_key(text, model_name, dimension)
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        response = self._call_with_retry(text, model_name=model_name, dimension=dimension, is_batch=False)

        embedding = response.output["embeddings"][0]["embedding"]

        if dimension is not None and len(embedding) != dimension:
            raise ValueError(
                f"API 返回向量维度与请求不匹配: "
                f"请求 dimension={dimension}, 实际={len(embedding)}。"
                f"当前模型 {model_name} 可能不支持 dimension 参数。"
            )

        cache_service.set(cache_key, embedding, self.cache_ttl)
        return embedding

    def embed_batch(self, texts: List[str], batch_size: int = 10, db=None,
                    model_name_override: str = None, dimension_override: int = None) -> List[List[float]]:
        model_name = model_name_override or self._get_current_model_name(db)
        dimension = dimension_override if dimension_override is not None else self._get_current_dimension(db)

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
            batch = valid_texts[i: i + batch_size]

            cached_embeddings = []
            uncached_texts = []
            uncached_indices = []

            for idx, text in enumerate(batch):
                cache_key = self._get_cache_key(text, model_name, dimension)
                cached = cache_service.get(cache_key)
                if cached:
                    cached_embeddings.append((idx, cached))
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(idx)

            new_embeddings = []
            if uncached_texts:
                response = self._call_with_retry(uncached_texts, model_name=model_name,
                                                  dimension=dimension, is_batch=True)

                api_embeddings = response.output.get("embeddings", [])
                if len(api_embeddings) != len(uncached_texts):
                    raise ValueError(
                        f"API 返回向量数量不匹配: 请求 {len(uncached_texts)} 个，返回 {len(api_embeddings)} 个"
                    )

                for item in api_embeddings:
                    new_embeddings.append(item["embedding"])

                if new_embeddings and dimension is not None:
                    actual_dims = [len(emb) for emb in new_embeddings]
                    if any(d != dimension for d in actual_dims):
                        raise ValueError(
                            f"API 返回向量维度与请求不匹配: "
                            f"请求 dimension={dimension}, 实际={actual_dims}。"
                            f"当前模型 {model_name} 可能不支持 dimension 参数，"
                            f"请使用模型默认维度或确认 dashscope SDK 版本。"
                        )

                for text, embedding in zip(uncached_texts, new_embeddings):
                    cache_key = self._get_cache_key(text, model_name, dimension)
                    cache_service.set(cache_key, embedding, self.cache_ttl)

            batch_result = [None] * len(batch)
            for idx, emb in cached_embeddings:
                batch_result[idx] = emb
            for idx, emb in zip(uncached_indices, new_embeddings):
                batch_result[idx] = emb

            if None in batch_result:
                missing = batch_result.count(None)
                raise ValueError(f"批次向量化结果不完整: {missing}/{len(batch)} 个向量缺失")

            all_embeddings.extend(batch_result)

        if len(all_embeddings) != len(valid_texts):
            raise ValueError(
                f"向量化结果数量不匹配: 输入 {len(valid_texts)} 个文本，返回 {len(all_embeddings)} 个向量"
            )

        full_result = [[] for _ in texts]
        for valid_idx, original_idx in enumerate(original_indices):
            full_result[original_idx] = all_embeddings[valid_idx]

        return full_result
