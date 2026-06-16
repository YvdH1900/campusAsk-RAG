"""
向量存储服务（父子分块分离存储）
==============================
使用 Milvus 向量数据库存储和检索文档向量
支持 Parent-Child Chunking：
- 父块存储在 MySQL（避免 Milvus 冗余）
- 子块集合仅存储 parent_id 引用
- 检索时关联查询返回完整上下文
"""

from typing import List, Dict, Optional
import logging
import time
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility, MilvusException
from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储服务"""

    CHILD_COLLECTION_NAME = "document_children"
    TEMP_COLLECTION_NAME = "document_children_temp"
    DEFAULT_DIMENSION = 1024  # 默认向量维度

    def __init__(self, db=None, collection_name: str = None, dimension_override: int = None):
        """
        初始化向量存储
        
        Args:
            db: 数据库会话（可选，用于动态读取向量维度）
            collection_name: 集合名称（可选，用于操作临时集合）
            dimension_override: 覆盖向量维度（可选，用于强制指定新维度）
        """
        self.db = db
        self._collection_name = collection_name or self.CHILD_COLLECTION_NAME
        self.child_collection = None
        self._available = False
        self._dimension = dimension_override or self._get_current_dimension()
        self._initialize()

    def _get_current_dimension(self) -> int:
        """
        获取当前激活的 Embedding 模型的向量维度
        
        优先从数据库读取，其次从环境变量读取，最后使用默认值
        
        Returns:
            向量维度
        """
        # 优先尝试从数据库读取（即使没有传入 db 参数）
        try:
            from app.models import ModelConfig
            from app.core.database import SessionLocal
            
            temp_db = self.db
            if not temp_db:
                temp_db = SessionLocal()
            
            try:
                active_embedding = temp_db.query(ModelConfig).filter(
                    ModelConfig.model_type == "embedding",
                    ModelConfig.is_active == True
                ).first()
                
                if active_embedding and active_embedding.dimension:
                    logger.info(f"从数据库读取向量维度: {active_embedding.dimension}")
                    return active_embedding.dimension
            finally:
                if not self.db and temp_db:
                    temp_db.close()
        except Exception as e:
            logger.warning(f"读取数据库向量维度配置失败：{e}")
        
        # 从环境变量读取
        import os
        env_dimension = os.environ.get("EMBEDDING_DIMENSION")
        if env_dimension:
            try:
                dim = int(env_dimension)
                logger.info(f"从环境变量读取向量维度: {dim}")
                return dim
            except ValueError:
                logger.warning(f"环境变量 EMBEDDING_DIMENSION 值无效: {env_dimension}")
        
        # 从配置读取
        if hasattr(settings, "EMBEDDING_DIMENSION") and settings.EMBEDDING_DIMENSION:
            logger.info(f"从配置读取向量维度: {settings.EMBEDDING_DIMENSION}")
            return settings.EMBEDDING_DIMENSION
        
        # 使用默认维度
        logger.info(f"使用默认向量维度: {self.DEFAULT_DIMENSION}")
        return self.DEFAULT_DIMENSION

    @property
    def dimension(self) -> int:
        """获取当前向量维度"""
        return self._dimension

    def _initialize(self):
        """
        初始化连接和集合（带重试退避）
        
        冷启动时 Milvus 可能需要 30-90 秒才能完全就绪，
        这里会以指数退避重试连接，最大等待约 2 分钟。
        """
        max_retries = 6
        base_delay = 2
        
        self._available = False
        
        for attempt in range(1, max_retries + 1):
            try:
                self._connect()
                self._ensure_collection()
                self._available = True
                logger.info("Milvus 连接成功")
                return
            except MilvusException as e:
                wait = base_delay ** attempt
                if attempt < max_retries:
                    logger.warning(
                        f"Milvus 初始化失败（第 {attempt}/{max_retries} 次尝试）: {str(e)}，"
                        f"{wait}s 后重试..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"Milvus 初始化失败（已重试 {max_retries} 次）: {str(e)}"
                    )
                    self._available = False
            except Exception as e:
                wait = base_delay ** attempt
                if attempt < max_retries:
                    logger.warning(
                        f"Milvus 初始化异常（第 {attempt}/{max_retries} 次尝试）: {str(e)}，"
                        f"{wait}s 后重试..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"Milvus 初始化失败（已重试 {max_retries} 次）: {str(e)}"
                    )
                    self._available = False

    def _check_available(self):
        """检查 Milvus 是否可用"""
        if not self._available:
            raise RuntimeError("Milvus 服务不可用，请检查连接")
        try:
            utility.has_collection(self._collection_name)
            return True
        except Exception as e:
            logger.error(f"Milvus 连接测试失败: {str(e)}")
            self._available = False
            raise

    def _connect(self):
        """连接到 Milvus"""
        if not connections.has_connection("default"):
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                timeout=10,  # 连接超时 10 秒
            )

    def _ensure_collection(self):
        """确保集合存在且维度正确，且包含 split_group_id 字段"""
        if utility.has_collection(self._collection_name):
            existing_collection = Collection(self._collection_name)
            schema = existing_collection.schema
            field_names = [f.name for f in schema.fields]
            
            # 检查是否需要重建：维度不匹配 或 缺少 split_group_id 字段 或 字段长度不匹配
            need_rebuild = False
            rebuild_reason = ""
            
            for field in schema.fields:
                if field.name == "embedding":
                    existing_dim = field.params.get("dim")
                    if existing_dim != self._dimension:
                        need_rebuild = True
                        rebuild_reason = f"维度不匹配: 现有={existing_dim}, 期望={self._dimension}"
                    break
            
            if "split_group_id" not in field_names:
                need_rebuild = True
                rebuild_reason = "缺少 split_group_id 字段"
            
            # 检查字段长度是否匹配（设置为 65535 后不再需要检查）
            # 如果旧集合字段长度 < 65535，则重建
            for field in schema.fields:
                if field.name in ("parent_content", "child_content"):
                    existing_max_length = field.params.get("max_length")
                    if existing_max_length and existing_max_length < 65535:
                        need_rebuild = True
                        rebuild_reason = f"字段长度不足: {field.name} 现有={existing_max_length}, 需要 65535"
                        break
            
            if need_rebuild:
                logger.warning(
                    f"集合需要重建: {rebuild_reason}，"
                    f"自动重建集合（旧数据将被清除，需重新处理文档）"
                )
                utility.drop_collection(self._collection_name)
                self._create_child_collection()
                self.child_collection = Collection(self._collection_name)
                self.child_collection.load()
                return
        
        if not utility.has_collection(self._collection_name):
            self._create_child_collection()
        
        self.child_collection = Collection(self._collection_name)
        self.child_collection.load()

    def _reconnect(self):
        """重新连接 Milvus"""
        try:
            if connections.has_connection("default"):
                connections.disconnect("default")
        except Exception:
            pass
        self._available = False
        self._initialize()

    def _create_child_collection(self):
        """创建子块集合"""
        # Milvus VARCHAR 最大支持 65535，设置为最大值避免长度限制问题
        MAX_VARCHAR_LENGTH = 65535
        
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="document_id", dtype=DataType.INT64, description="文档ID"),
            FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=100, description="父块ID"),
            FieldSchema(name="child_id", dtype=DataType.VARCHAR, max_length=100, description="子块ID"),
            FieldSchema(name="parent_content", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LENGTH, description="父块内容（完整上下文）"),
            FieldSchema(name="child_content", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LENGTH, description="子块内容（用于检索匹配）"),
            FieldSchema(name="split_group_id", dtype=DataType.VARCHAR, max_length=200, description="拆分组ID（同源子文档共享）"),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._dimension, description="子块向量"),
        ]

        schema = CollectionSchema(fields, description="文档子块集合（向量检索）")
        collection = Collection(self._collection_name, schema)

        # 创建 HNSW 向量索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {
                "M": 16,
                "efConstruction": 200,
            },
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        
        # 创建文档ID和父块ID索引
        collection.create_index(field_name="document_id", index_name="doc_id_idx")
        collection.create_index(field_name="parent_id", index_name="parent_id_idx")
        collection.load()

    def _create_child_collection_with_dim(self, dimension: int):
        """使用指定维度创建子块集合（用于向量库重建）"""
        saved_dim = self._dimension
        self._dimension = dimension
        try:
            self._create_child_collection()
        finally:
            self._dimension = saved_dim

    def insert(
        self,
        document_id: int,
        chunks: List[Dict],
        embeddings: List[List[float]],
        split_group_id: Optional[str] = None,
    ) -> List[str]:
        """
        插入子块向量（父块内容内联存储，检索时去重）
        
        Args:
            document_id: 文档ID
            chunks: 父子块列表
            embeddings: 子块对应的向量列表
            split_group_id: 拆分组ID（同源子文档共享）
            
        Returns:
            插入的子块ID列表
        """
        if not chunks or not embeddings:
            return []

        if len(chunks) != len(embeddings):
            raise ValueError(f"向量数量不匹配: chunks={len(chunks)}, embeddings={len(embeddings)}")

        # 严格校验：检查是否有空向量（调用方应确保已过滤）
        empty_count = sum(1 for emb in embeddings if not emb or len(emb) == 0)
        if empty_count > 0:
            raise ValueError(
                f"发现 {empty_count}/{len(embeddings)} 个空向量，"
                f"调用方应确保传入的 chunks 和 embeddings 已过滤空内容"
            )

        logger.info(f"文档 {document_id}: {len(chunks)} 个向量待插入")

        if not self._available or self.child_collection is None:
            logger.warning("Milvus 不可用，跳过向量插入")
            return []

        try:
            self._check_available()
        except Exception:
            logger.warning("Milvus 连接不可用，尝试重新连接")
            self._reconnect()
            try:
                self._check_available()
            except Exception:
                logger.error("Milvus 重新连接失败，跳过向量插入")
                return []

        child_ids = []
        child_data = [[], [], [], [], [], [], [], []]
        
        for chunk, embedding in zip(chunks, embeddings):
            child_id = f"doc{document_id}_{chunk['child_id']}"
            child_ids.append(child_id)
            
            child_data[0].append(child_id)
            child_data[1].append(document_id)
            child_data[2].append(chunk["parent_id"])
            child_data[3].append(chunk["child_id"])
            child_data[4].append(chunk["parent_content"][:8000])
            child_data[5].append(chunk["child_content"][:4000])
            child_data[6].append(split_group_id or "")
            child_data[7].append(embedding)

        if child_data[0]:
            self.child_collection.insert(child_data)
            self.child_collection.flush()

        return child_ids

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_id: Optional[int] = None,
    ) -> List[Dict]:
        """
        向量检索（子块匹配，返回父块内容并去重）
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            document_id: 可选，限定在特定文档中检索
            
        Returns:
            检索结果列表，包含父块内容作为上下文
        """
        if not self._available or self.child_collection is None:
            logger.warning("Milvus 不可用，返回空结果")
            return []
        
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64},
        }

        expr = None
        if document_id is not None:
            expr = f"document_id == {document_id}"

        results = self.child_collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["document_id", "parent_id", "child_id", "parent_content", "child_content", "split_group_id"],
        )

        output = []
        seen_parent_ids = set()
        
        for hits in results:
            for hit in hits:
                parent_id = hit.entity.get("parent_id")
                
                # 去重：同一个父块只返回一次
                if parent_id in seen_parent_ids:
                    continue
                seen_parent_ids.add(parent_id)
                
                output.append({
                    "document_id": hit.entity.get("document_id"),
                    "parent_id": parent_id,
                    "child_id": hit.entity.get("child_id"),
                    "parent_content": hit.entity.get("parent_content"),
                    "child_content": hit.entity.get("child_content"),
                    "split_group_id": hit.entity.get("split_group_id") or "",
                    "score": hit.distance,
                })

        return output

    def search_by_split_group(
        self,
        split_group_id: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        exclude_document_ids: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        按拆分组检索（获取同源文档的相关块）
        
        用于扩展检索：当某个拆分文档命中时，补充同源其他文档的相关上下文。
        如果有 query_embedding，使用向量检索排序；否则返回所有子块。
        
        Args:
            split_group_id: 拆分组ID
            query_embedding: 查询向量（用于向量检索排序，可选）
            top_k: 返回结果数量
            exclude_document_ids: 要排除的文档ID列表（已命中的文档）
            
        Returns:
            同源文档的检索结果列表
        """
        if not self._available or self.child_collection is None:
            logger.warning("Milvus 不可用，返回空结果")
            return []
        
        if not split_group_id:
            return []
        
        # 构建基础过滤表达式
        base_expr = f'split_group_id == "{split_group_id}"'
        if exclude_document_ids:
            excluded = ",".join(str(did) for did in exclude_document_ids)
            base_expr += f" and document_id not in [{excluded}]"
        
        # 如果有查询向量，使用向量检索（有相关性排序）
        if query_embedding:
            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": 64},
            }
            
            results = self.child_collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=base_expr,
                output_fields=["document_id", "parent_id", "child_id", "parent_content", "child_content", "split_group_id"],
            )
            
            output = []
            seen_parent_ids = set()
            
            for hits in results:
                for hit in hits:
                    parent_id = hit.entity.get("parent_id")
                    if parent_id in seen_parent_ids:
                        continue
                    seen_parent_ids.add(parent_id)
                    
                    output.append({
                        "document_id": hit.entity.get("document_id"),
                        "parent_id": parent_id,
                        "child_id": hit.entity.get("child_id"),
                        "parent_content": hit.entity.get("parent_content"),
                        "child_content": hit.entity.get("child_content"),
                        "split_group_id": hit.entity.get("split_group_id") or "",
                        "score": hit.distance,
                    })
            
            return output
        
        # 无查询向量时，简单查询返回（用于兜底）
        results = self.child_collection.query(
            expr=base_expr,
            output_fields=["document_id", "parent_id", "child_id", "parent_content", "child_content", "split_group_id"],
            limit=1000,
        )
        
        if not results:
            return []
        
        output = []
        seen_parent_ids = set()
        
        for item in results[:top_k]:
            parent_id = item.get("parent_id")
            if parent_id in seen_parent_ids:
                continue
            seen_parent_ids.add(parent_id)
            
            output.append({
                "document_id": item.get("document_id"),
                "parent_id": parent_id,
                "child_id": item.get("child_id"),
                "parent_content": item.get("parent_content"),
                "child_content": item.get("child_content"),
                "split_group_id": item.get("split_group_id") or "",
                "score": 0.0,
            })
        
        return output

    def delete_by_document_id(self, document_id: int):
        """
        删除指定文档的所有向量
        
        Args:
            document_id: 文档ID
        """
        self._check_available()
        self.child_collection.load()
        
        # 先查询要删除的向量ID列表
        expr = f"document_id == {document_id}"
        results = self.child_collection.query(
            expr=expr,
            output_fields=["id"]
        )
        
        if not results:
            logger.warning(f"未找到文档 {document_id} 的向量数据")
            return
        
        # 获取所有要删除的ID
        ids_to_delete = [r["id"] for r in results]
        count = len(ids_to_delete)
        logger.info(f"准备删除文档 {document_id} 的 {count} 条向量数据")
        
        # 分批删除，避免单次删除过多
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, count, batch_size):
            batch = ids_to_delete[i:i+batch_size]
            delete_expr = f"id in {batch}"
            self.child_collection.delete(delete_expr)
            deleted_count += len(batch)
            logger.info(f"已删除批次 {i//batch_size + 1}: {len(batch)} 条")
        
        self.child_collection.flush()
        
        # 执行 compaction 确保删除生效
        try:
            self.child_collection.compact()
            self.child_collection.wait_for_compaction_completed(timeout=30)
            logger.info(f"文档 {document_id} compaction 完成")
        except Exception as e:
            logger.warning(f"compaction 失败: {str(e)}")
        
        # 验证删除结果
        remaining = self.child_collection.query(
            expr=expr,
            output_fields=["id"]
        )
        
        if remaining:
            logger.error(f"删除文档 {document_id} 向量失败，仍有 {len(remaining)} 条数据")
        else:
            logger.info(f"已删除文档向量: document_id={document_id}, 共 {deleted_count} 条")

    def delete_orphan_vectors(self):
        """删除所有 document_id 无效（0 或 null）的孤儿向量"""
        self._check_available()#检查向量库是否可用
        self.child_collection.load()#加载子集合
        try:
            # 查询所有有效向量（document_id > 0）
            valid_results = self.child_collection.query(
                expr="document_id > 0",
                output_fields=["id", "document_id"]
            )
            valid_ids = set(r["id"] for r in valid_results)#有效向量ID集合
            
            # 查询所有无效向量（document_id <= 0 或 null）
            orphan_results = self.child_collection.query(
                expr="document_id <= 0",
                output_fields=["id"]
            )
            orphan_ids = [r["id"] for r in orphan_results]#无效向量ID列表
            
            if not orphan_ids:
                logger.info("没有孤儿向量，无需清理")
                return 0
            
            logger.info(f"发现 {len(orphan_ids)} 条孤儿向量，开始清理...")
            
            # 分批删除孤儿向量
            batch_size = 100#分批删除的向量数量
            deleted = 0#已删除的向量数量
            for i in range(0, len(orphan_ids), batch_size):
                batch = orphan_ids[i:i+batch_size]#当前批次的无效向量ID列表
                delete_expr = f"id in {batch}"
                self.child_collection.delete(delete_expr)#删除当前批次的无效向量
                deleted += len(batch)
            
            self.child_collection.flush()#刷新向量库，确保删除生效
            
            # 验证清理结果
            remaining_orphans = self.child_collection.query(
                expr="document_id <= 0",
                output_fields=["id"]
            )
            logger.info(f"孤儿向量清理完成，删除了 {deleted} 条，剩余 {len(remaining_orphans)} 条孤儿向量")
            return deleted
        except Exception as e:
            logger.warning(f"清理孤儿向量失败: {str(e)}")
            return 0

    def drop_collection(self):
        """删除集合（用于重置）"""
        if utility.has_collection(self._collection_name):
            utility.drop_collection(self._collection_name)
