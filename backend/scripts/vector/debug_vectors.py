"""
向量库详细检查脚本
==================
检查向量库中的所有数据，包括document_id等字段
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from pymilvus import connections, Collection, utility

def main():
    print("=" * 60)
    print("向量库详细检查")
    print("=" * 60)
    
    try:
        if not connections.has_connection("default"):
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
            )
        
        collection_name = "document_children"
        
        if not utility.has_collection(collection_name):
            print(f"集合 '{collection_name}' 不存在")
            return
        
        collection = Collection(collection_name)
        collection.load()
        
        total = collection.num_entities
        print(f"\n总向量数: {total}")
        
        if total == 0:
            print("向量库为空")
            return
        
        # 查询所有向量的详细信息
        print("\n查询所有向量详细信息...")
        
        # 使用不同的查询方式
        try:
            # 方法1: 查询 document_id > 0 的有效向量
            valid_results = collection.query(
                expr="document_id > 0",
                output_fields=["id", "document_id", "parent_id", "child_id"]
            )
            print(f"\n有效向量 (document_id > 0): {len(valid_results)} 条")
            for r in valid_results:
                print(f"  ID: {r['id']}, document_id: {r['document_id']}")
        except Exception as e:
            print(f"查询有效向量失败: {e}")
        
        try:
            # 方法2: 查询 document_id <= 0 的孤儿向量
            orphan_results = collection.query(
                expr="document_id <= 0",
                output_fields=["id", "document_id", "parent_id", "child_id"]
            )
            print(f"\n孤儿向量 (document_id <= 0): {len(orphan_results)} 条")
            for r in orphan_results:
                print(f"  ID: {r['id']}, document_id: {r['document_id']}")
        except Exception as e:
            print(f"查询孤儿向量失败: {e}")
        
        try:
            # 方法3: 查询所有向量（使用 id != '' 可能不工作）
            # Milvus 的 VARCHAR 主键需要使用不同的查询方式
            all_results = collection.query(
                expr='id like "%"',
                output_fields=["id", "document_id"]
            )
            print(f"\n所有向量 (id like '%'): {len(all_results)} 条")
            for r in all_results[:10]:
                print(f"  ID: {r['id']}, document_id: {r['document_id']}")
            if len(all_results) > 10:
                print(f"  ... 还有 {len(all_results) - 10} 条")
        except Exception as e:
            print(f"查询所有向量失败: {e}")
        
        # 检查集合统计信息
        print(f"\n集合统计信息:")
        print(f"  num_entities: {collection.num_entities}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
