"""
文档数量检查脚本
================
检查文档在本地文件、MySQL数据库和Milvus向量库中的数量
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.database import SessionLocal
from app.models import Document
from app.core.config import settings
from pymilvus import connections, Collection, utility

def check_local_files():
    """检查本地文件数量"""
    print("=" * 60)
    print("本地文件检查")
    print("=" * 60)
    
    upload_dirs = [
        "uploads/documents",
        "uploads/temp_documents"
    ]
    
    total_files = 0
    for dir_path in upload_dirs:
        if os.path.exists(dir_path):
            files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
            count = len(files)
            total_files += count
            print(f"  {dir_path}: {count} 个文件")
            if files:
                print(f"    文件列表:")
                for f in files[:10]:  # 只显示前10个
                    print(f"      - {f}")
                if len(files) > 10:
                    print(f"      ... 还有 {len(files) - 10} 个文件")
        else:
            print(f"  {dir_path}: 目录不存在")
    
    print(f"\n  总计: {total_files} 个本地文件")
    return total_files


def check_database():
    """检查数据库中的文档数量"""
    print("\n" + "=" * 60)
    print("数据库检查")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # 总文档数
        total = db.query(Document).count()
        print(f"  总文档数: {total}")
        
        # 按状态统计
        status_counts = {}
        for doc in db.query(Document).all():
            status = doc.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n  按处理状态统计:")
        for status, count in sorted(status_counts.items()):
            status_labels = {
                "pending": "待处理",
                "processing": "处理中",
                "completed": "已完成",
                "failed": "失败"
            }
            print(f"    {status_labels.get(status, status)}: {count}")
        
        # 按审核状态统计
        review_counts = {}
        for doc in db.query(Document).all():
            review_status = doc.review_status
            review_counts[review_status] = review_counts.get(review_status, 0) + 1
        
        print(f"\n  按审核状态统计:")
        for status, count in sorted(review_counts.items()):
            review_labels = {
                "pending": "待审核",
                "approved": "已通过",
                "rejected": "已驳回"
            }
            print(f"    {review_labels.get(status, status)}: {count}")
        
        # 显示文档详情
        print(f"\n  文档详情:")
        documents = db.query(Document).order_by(Document.id.desc()).all()
        for doc in documents[:20]:  # 只显示前20个
            print(f"    ID: {doc.id}")
            print(f"      文件名: {doc.filename}")
            print(f"      状态: {doc.status}")
            print(f"      审核状态: {doc.review_status}")
            print(f"      文件路径: {doc.file_path}")
            print(f"      文件存在: {os.path.exists(doc.file_path)}")
            print()
        
        if len(documents) > 20:
            print(f"    ... 还有 {len(documents) - 20} 个文档")
        
        return total
    finally:
        db.close()


def check_vector_store():
    """检查向量库中的向量数量"""
    print("\n" + "=" * 60)
    print("向量库检查")
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
        
        if not utility.has_collection(collection_name):
            print(f"  集合 '{collection_name}' 不存在")
            return 0
        
        collection = Collection(collection_name)
        collection.load()
        
        # 查询所有有效向量（document_id > 0）
        results = collection.query(
            expr="document_id > 0",
            output_fields=["id", "document_id"]
        )
        
        # 查询所有孤儿向量（document_id <= 0）
        orphan_results = collection.query(
            expr="document_id <= 0",
            output_fields=["id", "document_id"]
        )
        
        # 使用实际查询结果统计，而不是 num_entities（可能有延迟）
        total = len(results) + len(orphan_results)
        print(f"  总向量数: {total}")
        
        # 按文档ID统计
        doc_counts = {}
        for r in results:
            doc_id = r["document_id"]
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        
        print(f"\n  按文档ID统计:")
        if doc_counts:
            for doc_id, count in sorted(doc_counts.items()):
                print(f"    文档 {doc_id}: {count} 个向量")
        else:
            print("    无")
        
        # 检查孤儿向量
        if orphan_results:
            print(f"\n  孤儿向量 (document_id <= 0): {len(orphan_results)}")
            for r in orphan_results[:10]:
                print(f"    - ID: {r['id']}")
        
        return total
    except Exception as e:
        print(f"  错误: 无法连接到Milvus - {str(e)}")
        return 0


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("CampusAsk-RAG 文档数量检查报告")
    print("=" * 60 + "\n")
    
    local_count = check_local_files()
    db_count = check_database()
    vector_count = check_vector_store()
    
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    print(f"  本地文件数: {local_count}")
    print(f"  数据库文档数: {db_count}")
    print(f"  向量库向量数: {vector_count}")
    
    if db_count > 0 and local_count != db_count:
        print(f"\n  警告: 本地文件数与数据库文档数不匹配")
        print(f"     差异: {abs(local_count - db_count)} 个")
    
    if db_count > 0 and vector_count == 0:
        print(f"\n  警告: 数据库有文档但向量库为空")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
