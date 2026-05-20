"""
添加问题统计表迁移脚本

创建 question_stats 表，并用现有消息数据初始化问题统计
（不随会话删除而减少）
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# 加载 .env 文件
env_path = backend_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)

from sqlalchemy import create_engine, text
import os

# 延迟导入
from app.core.config import settings

def migrate():
    """执行数据库迁移"""
    print("开始迁移：创建 question_stats 表并初始化数据")
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # 1. 创建 question_stats 表（如果不存在）
            print("[INFO] 创建 question_stats 表...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS question_stats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    content VARCHAR(500) NOT NULL,
                    count INT DEFAULT 1 NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    UNIQUE KEY uk_question_stats_content (content(255)),
                    INDEX idx_question_stats_count (count)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问题统计表'
            """))
            conn.commit()
            print("[OK] question_stats 表创建成功")
            
            # 2. 如果表已存在，修复字段类型和索引
            print("[INFO] 检查并修复表结构...")
            try:
                # 检查 content 字段类型是否为 TEXT，如果是则改为 VARCHAR(500)
                result = conn.execute(text("""
                    SELECT COLUMN_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'question_stats' 
                    AND COLUMN_NAME = 'content'
                """))
                row = result.fetchone()
                if row and 'text' in row[0].lower():
                    conn.execute(text("ALTER TABLE question_stats MODIFY COLUMN content VARCHAR(500) NOT NULL"))
                    print("[OK] content 字段已改为 VARCHAR(500)")
            except Exception as e:
                print(f"[WARN] 检查字段类型时出错: {e}")
            
            try:
                # 检查是否存在唯一键
                result = conn.execute(text("""
                    SELECT CONSTRAINT_NAME 
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'question_stats' 
                    AND CONSTRAINT_TYPE = 'UNIQUE'
                    AND CONSTRAINT_NAME = 'uk_question_stats_content'
                """))
                if not result.fetchone():
                    # 清理重复数据（合并首尾空格不同的重复项）
                    print("[INFO] 正在清理重复问题数据...")
                    conn.execute(text("""
                        UPDATE question_stats 
                        SET content = TRIM(content)
                    """))
                    conn.execute(text("""
                        DELETE t1 FROM question_stats t1
                        INNER JOIN question_stats t2 
                        WHERE t1.id > t2.id 
                        AND TRIM(t1.content) = TRIM(t2.content)
                    """))
                    conn.commit()
                    
                    # 合并被删除记录的计数到保留的记录
                    conn.execute(text("""
                        UPDATE question_stats t1
                        INNER JOIN (
                            SELECT TRIM(content) as clean_content, SUM(count) as total_count,
                                   MIN(created_at) as min_created, MAX(updated_at) as max_updated
                            FROM question_stats
                            GROUP BY TRIM(content)
                        ) t2 ON TRIM(t1.content) = t2.clean_content
                        SET t1.count = t2.total_count,
                            t1.created_at = t2.min_created,
                            t1.updated_at = t2.max_updated
                    """))
                    
                    # 再次删除重复项
                    conn.execute(text("""
                        DELETE t1 FROM question_stats t1
                        INNER JOIN question_stats t2 
                        WHERE t1.id > t2.id 
                        AND TRIM(t1.content) = TRIM(t2.content)
                    """))
                    conn.commit()
                    print("[OK] 重复数据清理完成")
                    
                    # 检查并删除旧的普通索引（如果存在）
                    result = conn.execute(text("""
                        SELECT INDEX_NAME 
                        FROM INFORMATION_SCHEMA.STATISTICS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'question_stats' 
                        AND INDEX_NAME = 'idx_question_stats_content'
                    """))
                    if result.fetchone():
                        conn.execute(text("ALTER TABLE question_stats DROP INDEX idx_question_stats_content"))
                        print("[OK] 已删除旧索引 idx_question_stats_content")
                    # 添加唯一键
                    conn.execute(text("ALTER TABLE question_stats ADD UNIQUE KEY uk_question_stats_content (content(255))"))
                    print("[OK] 已添加唯一键 uk_question_stats_content")
            except Exception as e:
                print(f"[WARN] 添加唯一键时出错: {e}")
            
            conn.commit()
            
            # 3. 用现有消息数据初始化问题统计
            print("[INFO] 正在从现有消息数据初始化问题统计...")
            conn.execute(text("""
                INSERT INTO question_stats (content, count, created_at, updated_at)
                SELECT 
                    m.content,
                    COUNT(*) as count,
                    MIN(m.created_at) as created_at,
                    MAX(m.created_at) as updated_at
                FROM messages m
                WHERE m.role = 'user'
                GROUP BY m.content
                ON DUPLICATE KEY UPDATE 
                    count = count + VALUES(count),
                    updated_at = VALUES(updated_at)
            """))
            conn.commit()
            
            # 4. 显示初始化结果
            result = conn.execute(text("SELECT COUNT(*) as total FROM question_stats"))
            row = result.fetchone()
            total = row[0] if row else 0
            print(f"[OK] 已初始化 {total} 条问题统计记录")
        
        print("\n[SUCCESS] 迁移完成！")
        
    except Exception as e:
        print(f"\n[ERROR] 迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()
