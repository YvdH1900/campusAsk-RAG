"""
添加 can_modify_profile 字段到 users 表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import engine
from sqlalchemy import text

def add_column():
    """添加 can_modify_profile 字段"""
    with engine.connect() as conn:
        try:
            # 检查字段是否已存在
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'can_modify_profile'
            """))
            
            count = result.scalar()
            
            if count > 0:
                print("can_modify_profile 字段已存在")
                return
            
            # 添加字段
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN can_modify_profile BOOLEAN NOT NULL DEFAULT TRUE 
                COMMENT '是否允许修改个人信息'
            """))
            
            conn.commit()
            print("成功添加 can_modify_profile 字段")
            
        except Exception as e:
            print(f"添加字段失败：{e}")
            raise

if __name__ == "__main__":
    add_column()
