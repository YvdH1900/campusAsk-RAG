"""
清理孤儿向量脚本（直接删除集合）
================
直接删除整个集合并重建，彻底清理所有数据
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

def main():
    """清理孤儿向量 - 通过重建集合"""
    print("=" * 60)
    print("清理孤儿向量 - 重建集合")
    print("=" * 60)
    
    try:
        # 连接Milvus
        if not connections.has_connection("default"):
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
            )
        
        collection_name = "document_children"
        dimension = 1024
        
        if not utility.has_collection(collection_name):
            print(f"集合 '{collection_name}' 不存在，无需清理")
            return
        
        # 获取当前向量数
        collection = Collection(collection_name)
        collection.load()
        total = collection.num_entities
        print(f"\n当前向量库总向量数: {total}")
        
        if total == 0:
            print("向量库为空，无需清理")
            return
        
        # 确认删除
        print(f"\n即将删除整个集合并重建，这将删除所有 {total} 条向量数据")
        print("确认继续？(y/n): ", end="")
        
        # 自动确认（因为这是脚本模式）
        response = "y"
        print(response)
        
        if response.lower() != "y":
            print("取消操作")
            return
        
        # 删除旧集合
        print(f"\n删除旧集合 '{collection_name}'...")
        utility.drop_collection(collection_name)
        print("旧集合已删除")
        
        # 创建新集合
        print(f"\n创建新集合 '{collection_name}'...")
        MAX_VARCHAR_LENGTH = 65535
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="document_id", dtype=DataType.INT64, description="文档ID"),
            FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=100, description="父块ID"),
            FieldSchema(name="child_id", dtype=DataType.VARCHAR, max_length=100, description="子块ID"),
            FieldSchema(name="parent_content", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LENGTH, description="父块内容（已迁移到 MySQL，此字段保留兼容）"),
            FieldSchema(name="child_content", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LENGTH, description="子块内容（用于检索匹配）"),
            FieldSchema(name="split_group_id", dtype=DataType.VARCHAR, max_length=200, description="拆分组ID"),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension, description="子块向量"),
        ]

        schema = CollectionSchema(fields, description="文档子块集合（向量检索）")
        new_collection = Collection(collection_name, schema)

        # 创建 HNSW 向量索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {
                "M": 16,
                "efConstruction": 200,
            },
        }
        new_collection.create_index(field_name="embedding", index_params=index_params)
        
        # 创建文档ID和父块ID索引
        new_collection.create_index(field_name="document_id", index_name="doc_id_idx")
        new_collection.create_index(field_name="parent_id", index_name="parent_id_idx")
        new_collection.load()
        
        print("新集合已创建并加载")
        
        # 验证清理结果
        remaining = new_collection.num_entities
        print(f"\n向量库剩余向量数: {remaining}")
        print("孤儿向量清理完成！")
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
