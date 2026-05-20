"""
添加用户会话 ID 字段迁移脚本

为 users 表添加 current_session_id 字段，用于实现单点登录功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
import os

# 手动设置环境变量
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///./campus_ask.db')

# 延迟导入
from app.core.config import settings

def migrate():
    """执行数据库迁移"""
    print("开始迁移：添加 current_session_id 字段到 users 表")
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # 执行迁移 SQL
        with engine.connect() as conn:
            try:
                # 添加 current_session_id 字段（如果不存在）
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN current_session_id VARCHAR(100) DEFAULT NULL"
                ))
                print("[OK] 添加 current_session_id 字段")
            except Exception as e:
                if "Duplicate column name" in str(e) or "already exists" in str(e):
                    print("[SKIP] current_session_id 字段已存在")
                else:
                    raise
            
            try:
                # 添加索引以提高查询性能
                conn.execute(text(
                    "CREATE INDEX idx_users_current_session_id ON users(current_session_id)"
                ))
                print("[OK] 创建索引 idx_users_current_session_id")
            except Exception as e:
                if "Duplicate key name" in str(e) or "already exists" in str(e):
                    print("[SKIP] 索引已存在")
                else:
                    raise
            
            conn.commit()
        
        print("\n[SUCCESS] 迁移完成！")
        
    except Exception as e:
        print(f"[ERROR] 迁移失败：{str(e)}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    migrate()
    print("\n迁移完成！请重启后端服务以应用更改。")
