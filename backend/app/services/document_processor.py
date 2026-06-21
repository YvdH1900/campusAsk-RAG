"""
文档处理服务（重构版）
======================
整合新流水线：预处理 → 解析 → 清洗 → 分块 → 向量化 → 入库

新特性：
- 异步任务友好（支持进度回调）
- 三级清洗流水线集成
- 大文件拆分并行处理
- 低质量/无效内容自动拦截
- 事务回滚、缓存清理、错误重试
"""

import gc
import logging
import os
from typing import Optional, Callable, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.models import Document, ParentChunk
from app.services.document_parser import DocumentParser
from app.services.text_splitter import TextSplitter
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.cache_service import cache_service
from app.services.document_cleaner import document_cleaner
from app.services.document_preprocessor import document_preprocessor

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        self.parser = DocumentParser()
        self.splitter = TextSplitter()
        self.embedder = EmbeddingService()
        self.vector_store = None

    def _get_vector_store(self, db: Session):
        if self.vector_store is None:
            self.vector_store = VectorStore(db=db)
        return self.vector_store

    def _insert_parent_chunks(
        self,
        document_id: int,
        chunks: list,
        db: Session,
        split_group_id: str = None,
    ):
        """将父块去重后写入 MySQL parent_chunks 表"""
        seen_parents = set()
        parent_records = []

        for chunk in chunks:
            parent_id = chunk.get("parent_id")
            parent_content = chunk.get("parent_content", "")

            if not parent_id or parent_id in seen_parents:
                continue
            if not parent_content.strip():
                continue

            seen_parents.add(parent_id)
            parent_records.append(ParentChunk(
                document_id=document_id,
                parent_id=parent_id,
                parent_content=parent_content,
                split_group_id=split_group_id or "",
            ))

        if parent_records:
            db.add_all(parent_records)
            db.flush()
            logger.info(
                f"父块入库 MySQL: document_id={document_id}, "
                f"{len(parent_records)} 条父块"
            )

    def process_document(
        self,
        document: Document,
        db: Session,
        progress_callback: Optional[Callable] = None,
    ):
        """
        处理文档完整流水线：
        解析 → 粗洗 → 分块 → 精洗+校验 → 向量化 → 存储

        Args:
            document: 文档对象
            db: 数据库会话
            progress_callback: 进度回调 callback(current, total, stage)
        """
        def report_progress(current, total, stage):
            if progress_callback:
                progress_callback(current, total, stage)
            logger.info(f"进度: {stage} - {current}/{total}")

        try:
            if document.status in ("pending", "approved"):
                document.status = "processing"
                db.commit()

            file_path = document.file_path
            if not os.path.exists(file_path):
                raise ValueError(f"文件不存在: {file_path}")

            file_size = os.path.getsize(file_path)
            logger.info(f"开始处理文档: {document.filename} ({file_size / 1024 / 1024:.1f}MB)")

            # 1. 解析文档（含预处理 + 粗洗）
            report_progress(0, 100, "解析文档")
            text = self.parser.parse(file_path, preprocess=True, apply_coarse_clean=True)

            if not text or not text.strip():
                raise ValueError("文档解析后内容为空（可能已被预处理/清洗拦截）")

            logger.info(f"文档解析完成: {len(text)} 字符")

            # 检测语言
            lang = self.parser.detect_language(text)
            logger.info(f"文档语言: {lang}")

            # 2. 文本分块（含精洗 + 校验 + 轻校验）
            report_progress(20, 100, "分块处理")
            chunks = self.splitter.split(text)

            if not chunks:
                raise ValueError("文档分块后为空（所有块可能已被清洗拦截）")

            # 分块质量评估
            quality = self.splitter.evaluate_quality(chunks)
            logger.info(f"分块质量: {quality}")

            if quality["quality"] == "poor":
                logger.warning(
                    f"文档 {document.filename} 分块质量较差: "
                    f"子块过短({quality['too_short']}/{quality['total_children']}), "
                    f"子块过长({quality['too_long']}/{quality['total_children']}), "
                    f"平均子块大小={quality['avg_child_size']}字符"
                )
            elif quality["quality"] == "fair":
                logger.warning(
                    f"文档 {document.filename} 分块质量一般: "
                    f"子块过短({quality['too_short']}/{quality['total_children']})"
                )

            # 提取有效子块
            valid_chunks = [
                chunk for chunk in chunks
                if chunk.get("child_content", "").strip()
            ]
            if not valid_chunks:
                raise ValueError("文档分块后无有效内容")

            child_contents = [chunk["child_content"] for chunk in valid_chunks]
            parent_count = len(set(c["parent_id"] for c in valid_chunks))
            logger.info(
                f"文档 {document.filename} 分为 {len(chunks)} 个子块"
                f"（有效 {len(valid_chunks)} 个），对应 {parent_count} 个父块"
            )

            # 3. 向量化
            report_progress(40, 100, "向量化")
            logger.info(f"开始向量化: {document.filename}")

            all_embeddings = self.embedder.embed_batch(child_contents, db=db)

            # 4. 存储到向量数据库
            report_progress(80, 100, "存储向量")
            vector_store = self._get_vector_store(db)
            try:
                vector_store.insert(
                    document.id, valid_chunks, all_embeddings,
                    split_group_id=document.split_group_id,
                )
            except Exception as e:
                logger.error(f"向量入库失败，回滚文档状态: {document.filename}, 错误: {str(e)}")
                try:
                    vector_store.delete_by_document_id(document.id)
                    logger.info(f"已清理文档 {document.id} 的残留向量")
                except Exception as cleanup_error:
                    logger.warning(f"清理残留向量失败: {str(cleanup_error)}")
                document.status = "failed"
                db.commit()
                raise

            # 5. 父块写入 MySQL
            try:
                self._insert_parent_chunks(
                    document.id, valid_chunks, db,
                    split_group_id=document.split_group_id,
                )

                # 6. 更新状态
                document.status = "completed"
                db.commit()
            except Exception as e:
                logger.error(f"父块入库MySQL失败，回滚: {document.filename}, 错误: {str(e)}")
                db.rollback()
                # 清理已入库的 Milvus 向量，保持数据一致性
                try:
                    vector_store.delete_by_document_id(document.id)
                    logger.info(f"已清理文档 {document.id} 的残留向量（MySQL失败回滚）")
                except Exception as cleanup_error:
                    logger.warning(f"清理残留向量失败: {str(cleanup_error)}")
                document.status = "failed"
                db.commit()
                raise

            # 7. 清除缓存
            cache_service.clear_pattern("search:*")
            cache_service.clear_pattern(f"document:{document.id}:*")

            report_progress(100, 100, "完成")
            logger.info(
                f"文档处理完成: {document.filename}, "
                f"共 {len(valid_chunks)} 个子块, {parent_count} 个父块"
            )

            del text, chunks, child_contents, all_embeddings
            gc.collect()

        except Exception as e:
            try:
                document.status = "failed"
                db.commit()
            except Exception as db_error:
                logger.error(f"更新文档失败状态时出错: {str(db_error)}")
                db.rollback()

            logger.error(f"文档处理失败: {document.filename}, 错误: {str(e)}")
            raise

    def process_split_document(
        self,
        document: Document,
        split_files: list,
        db: Session,
        progress_callback: Optional[Callable] = None,
    ):
        """
        处理拆分文档：逐个处理拆分文件，向量共享同一个 document_id

        Args:
            document: 文档对象
            split_files: 拆分后的文件路径列表
            db: 数据库会话
            progress_callback: 进度回调
        """
        def report_progress(current, total, stage):
            if progress_callback:
                progress_callback(current, total, stage)
            logger.info(f"进度: {stage} - {current}/{total}")

        try:
            if document.status in ("pending", "approved"):
                document.status = "processing"
                db.commit()

            vector_store = self._get_vector_store(db)
            total_files = len(split_files)
            all_valid_chunks = []
            all_embeddings = []

            # ---- 阶段1：并行解析 + 分块（I/O 密集型，使用线程池） ----
            def _parse_and_split(idx_split_path):
                """单个拆分文件的解析+分块，在子线程中执行"""
                idx, split_path = idx_split_path
                split_name = os.path.basename(split_path)
                logger.info(f"处理拆分文件 [{idx+1}/{total_files}]: {split_name}")

                text = self.parser.parse(split_path, preprocess=True, apply_coarse_clean=True)
                if not text or not text.strip():
                    logger.warning(f"拆分文件内容为空，跳过: {split_name}")
                    return idx, []

                chunks = self.splitter.split(text, parent_id_prefix=f"s{idx}_")
                if not chunks:
                    logger.warning(f"拆分文件分块后为空，跳过: {split_name}")
                    return idx, []

                valid = [c for c in chunks if c.get("child_content", "").strip()]
                if not valid:
                    logger.warning(f"拆分文件无有效内容，跳过: {split_name}")
                    return idx, []

                logger.info(f"拆分文件 {split_name}: {len(valid)} 个有效子块")
                return idx, valid

            report_progress(0, 100, f"并行解析 {total_files} 个拆分文件")
            max_workers = min(total_files, os.cpu_count() or 4)
            parallel_results = {}

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_parse_and_split, (idx, sp)): idx
                    for idx, sp in enumerate(split_files)
                }
                for future in as_completed(futures):
                    try:
                        idx, valid_chunks = future.result()
                        if valid_chunks:
                            parallel_results[idx] = valid_chunks
                    except Exception as e:
                        logger.error(f"拆分文件并行处理异常: {str(e)}")

            # 按原始顺序合并结果
            for idx in sorted(parallel_results.keys()):
                valid_chunks = parallel_results[idx]
                child_contents = [chunk["child_content"] for chunk in valid_chunks]

                # 2. 向量化
                report_progress(
                    (idx + 1) * 50 // total_files, 100,
                    f"向量化文件 {idx+1}/{total_files}",
                )
                embeddings = self.embedder.embed_batch(child_contents, db=db)

                all_valid_chunks.extend(valid_chunks)
                all_embeddings.extend(embeddings)

            if not all_valid_chunks:
                raise ValueError("所有拆分文件处理后均无有效内容")

            logger.info(
                f"拆分文档处理完成: {document.filename}, "
                f"{total_files} 个子文件, 共 {len(all_valid_chunks)} 个子块"
            )

            # 4. 存储向量
            report_progress(80, 100, "存储向量")
            try:
                vector_store.insert(
                    document.id, all_valid_chunks, all_embeddings,
                    split_group_id=document.split_group_id,
                )
            except Exception as e:
                logger.error(f"向量入库失败，回滚: {document.filename}, 错误: {str(e)}")
                try:
                    vector_store.delete_by_document_id(document.id)
                except Exception as cleanup_error:
                    logger.warning(f"清理残留向量失败: {str(cleanup_error)}")
                document.status = "failed"
                db.commit()
                raise

            # 5. 父块写入 MySQL
            try:
                self._insert_parent_chunks(
                    document.id, all_valid_chunks, db,
                    split_group_id=document.split_group_id,
                )

                # 6. 更新状态
                document.status = "completed"
                db.commit()
            except Exception as e:
                logger.error(f"拆分文档父块入库MySQL失败，回滚: {document.filename}, 错误: {str(e)}")
                db.rollback()
                # 清理已入库的 Milvus 向量，保持数据一致性
                try:
                    vector_store.delete_by_document_id(document.id)
                    logger.info(f"已清理文档 {document.id} 的残留向量（MySQL失败回滚）")
                except Exception as cleanup_error:
                    logger.warning(f"清理残留向量失败: {str(cleanup_error)}")
                document.status = "failed"
                db.commit()
                raise

            # 7. 清除缓存
            cache_service.clear_pattern("search:*")
            cache_service.clear_pattern(f"document:{document.id}:*")

            report_progress(100, 100, "完成")
            logger.info(
                f"拆分文档处理完成: {document.filename}, "
                f"共 {len(all_valid_chunks)} 个子块"
            )

            del all_valid_chunks, all_embeddings
            gc.collect()

        except Exception as e:
            try:
                document.status = "failed"
                db.commit()
            except Exception as db_error:
                logger.error(f"更新文档失败状态时出错: {str(db_error)}")
                db.rollback()

            logger.error(f"拆分文档处理失败: {document.filename}, 错误: {str(e)}")
            raise

        finally:
            # 无论成功或失败，都要清理拆分临时文件
            for split_path in split_files:
                try:
                    os.remove(split_path)
                    logger.info(f"已清理拆分文件: {split_path}")
                except Exception:
                    pass

    def delete_document_vectors(self, document_id: int, db=None):
        """删除文档的向量数据和父块"""
        try:
            vector_store = self._get_vector_store(db) if db else VectorStore()
            vector_store.delete_by_document_id(document_id)

            if db:
                deleted = db.query(ParentChunk).filter(
                    ParentChunk.document_id == document_id
                ).delete()
                db.commit()
                if deleted:
                    logger.info(f"已删除文档父块: document_id={document_id}, {deleted} 条")

            cache_service.clear_pattern(f"document:{document_id}:*")
            logger.info(f"已删除文档向量: document_id={document_id}")
        except Exception as e:
            logger.error(f"删除文档向量失败: document_id={document_id}, 错误: {str(e)}")

    def check_parent_chunks_integrity(self, db: Session) -> Dict:
        """
        检查 MySQL parent_chunks 与 Milvus 子块的数据一致性
        
        Returns:
            {
                "ok": bool,
                "milvus_pairs": int,      # Milvus 中唯一切片对数量
                "mysql_pairs": int,       # MySQL 中父块记录数
                "missing": List[Dict],    # 缺失的记录: [{document_id, parent_id}, ...]
                "orphan_mysql": List[Dict], # MySQL 中多余（Milvus 已删除）的记录
            }
        """
        result = {"ok": False, "milvus_pairs": 0, "mysql_pairs": 0, "missing": [], "orphan_mysql": []}
        
        try:
            vector_store = self._get_vector_store(db)
            
            # 1. 从 Milvus 收集所有 (document_id, parent_id) 对
            entities = vector_store.child_collection.query(
                expr="document_id > 0",
                output_fields=["document_id", "parent_id"],
                limit=10000,
            )
            milvus_pairs = set()
            for e in entities:
                did = e.get("document_id")
                pid = e.get("parent_id")
                if did is not None and pid:
                    milvus_pairs.add((int(did), str(pid)))
            result["milvus_pairs"] = len(milvus_pairs)
            
            # 2. 从 MySQL 收集所有 (document_id, parent_id) 对
            mysql_rows = db.query(ParentChunk).all()
            mysql_pairs = {}
            for row in mysql_rows:
                key = (row.document_id, row.parent_id)
                mysql_pairs[key] = row
            result["mysql_pairs"] = len(mysql_pairs)
            
            # 3. 找出 Milvus 有而 MySQL 没有的（核心问题：父块回填会 miss）
            for pair in milvus_pairs:
                if pair not in mysql_pairs:
                    result["missing"].append({"document_id": pair[0], "parent_id": pair[1]})
            
            # 4. 找出 MySQL 有而 Milvus 没有的（可能文档已删除但父块残留）
            for pair in mysql_pairs:
                if pair not in milvus_pairs:
                    result["orphan_mysql"].append({"document_id": pair[0], "parent_id": pair[1]})
            
            result["ok"] = len(result["missing"]) == 0
            
            if not result["ok"]:
                logger.warning(
                    f"数据完整性检查: {len(result['missing'])} 个 Milvus 子块缺少 MySQL 父块记录, "
                    f"{len(result['orphan_mysql'])} 条 MySQL 孤立记录"
                )
                for m in result["missing"][:10]:  # 最多打印10条
                    logger.warning(f"  缺失: document_id={m['document_id']}, parent_id={m['parent_id']}")
            else:
                logger.info(f"数据完整性检查通过: {result['milvus_pairs']} 对一致")
            
            return result
            
        except Exception as e:
            logger.error(f"数据完整性检查失败: {e}")
            return result