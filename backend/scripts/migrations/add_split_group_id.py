"""
数据库迁移脚本：为 documents 表添加 split_group_id 字段
====================================================
用法:
    python backend/scripts/migrations/add_split_group_id.py

注意:
    - 运行前确保数据库连接配置正确
    - 此脚本会修改数据库表结构，建议先备份
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import text
from app.core.database import engine


def add_split_group_id_column():
    """为 documents 表添加 split_group_id 字段"""
    print("开始迁移：为 documents 表添加 split_group_id 字段...")
    
    with engine.connect() as conn:
        # 检查字段是否已存在
        result = conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'documents' 
            AND COLUMN_NAME = 'split_group_id'
        """))
        
        column_exists = result.scalar() > 0
        
        if column_exists:
            print("✓ split_group_id 字段已存在，跳过")
            return
        
        # 添加字段
        conn.execute(text("""
            ALTER TABLE documents 
            ADD COLUMN split_group_id VARCHAR(100) NULL 
            COMMENT '拆分组ID（同源子文档共享同一ID）'
        """))
        
        # 添加索引
        conn.execute(text("""
            CREATE INDEX idx_documents_split_group_id 
            ON documents(split_group_id)
        """))
        
        conn.commit()
        print("✓ split_group_id 字段添加成功")
        print("✓ 索引创建成功")


def backfill_split_group_id():
    """为已有的拆分文档回填 split_group_id"""
    print("\n开始回填：为已有的拆分文档设置 split_group_id...")
    
    with engine.connect() as conn:
        # 查找文件名包含 _part 的文档（这些是拆分后的子文档）
        result = conn.execute(text("""
            SELECT id, filename FROM documents 
            WHERE filename LIKE '%_part%' 
            AND (split_group_id IS NULL OR split_group_id = '')
        """))
        
        rows = result.fetchall()
        
        if not rows:
            print("✓ 没有需要回填的拆分文档")
            return
        
        print(f"找到 {len(rows)} 个需要回填的拆分文档")
        
        updated = 0
        for doc_id, filename in rows:
            # 从文件名提取原文档名（去掉 _partXX.pdf 后缀）
            import re
            match = re.match(r"^(.+)_part\d+", filename)
            if match:
                original_name = match.group(1)
                # 使用原文档名作为 split_group_id
                conn.execute(text("""
                    UPDATE documents 
                    SET split_group_id = :group_id 
                    WHERE id = :doc_id
                """), {"group_id": original_name, "doc_id": doc_id})
                updated += 1
        
        conn.commit()
        print(f"✓ 已回填 {updated} 个文档的 split_group_id")


if __name__ == "__main__":
    try:
        add_split_group_id_column()
        backfill_split_group_id()
        print("\n✓ 迁移完成！")
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        sys.exit(1)
