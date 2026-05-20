"""
添加 file_size 字段到 documents 表
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def add_file_size_column():
    """添加 file_size 列到 documents 表"""
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # 检查列是否已存在
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('documents')]
        
        if 'file_size' in columns:
            print("[OK] file_size 列已存在")
            return
        
        print("开始添加 file_size 列到 documents 表...")
        
        # 执行 ALTER TABLE 语句
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE documents ADD COLUMN file_size INTEGER DEFAULT 0 NOT NULL COMMENT '文件大小 (字节)'"
            ))
            conn.commit()
        
        print("[OK] file_size 列添加成功")
        
    except Exception as e:
        print(f"[ERROR] 添加列失败：{str(e)}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    add_file_size_column()
    print("\n数据库迁移完成！")
