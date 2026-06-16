"""
删除旧的 Milvus 集合
=====================
用于修复 schema 不匹配问题（缺少 split_group_id 字段）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from pymilvus import connections, utility

def main():
    print("=" * 60)
    print("删除旧的 Milvus 集合")
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
            print(f"集合 '{collection_name}' 不存在，无需删除")
            return
        
        print("\n[WARNING] 这将删除所有已存储的向量数据！")
        print("    删除后需要重新处理文档以重建向量库。")
        
        confirm = input("\n确认删除？(yes/no): ")
        if confirm.lower() != "yes":
            print("操作已取消")
            return
        
        utility.drop_collection(collection_name)
        print(f"\n[OK] 集合 '{collection_name}' 已删除")
        print("下次启动时会自动创建包含 split_group_id 字段的新集合")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
