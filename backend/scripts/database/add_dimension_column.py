"""
添加 dimension 字段到 model_configs 表
用于支持不同 Embedding 模型的向量维度
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def add_dimension_column():
    """添加 dimension 列到 model_configs 表"""
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # 检查列是否已存在
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('model_configs')]
        
        if 'dimension' in columns:
            print("[OK] dimension 列已存在")
            return
        
        print("开始添加 dimension 列到 model_configs 表...")
        
        # 执行 ALTER TABLE 语句
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE model_configs ADD COLUMN dimension INTEGER DEFAULT NULL COMMENT '向量维度（仅 embedding 模型）'"
            ))
            conn.commit()
        
        print("[OK] dimension 列添加成功")
        
        # 为现有的 embedding 模型设置默认维度
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT id, model_name FROM model_configs WHERE model_type = 'embedding'"
            ))
            rows = result.fetchall()
            
            if rows:
                print(f"\n发现 {len(rows)} 个现有的 Embedding 模型配置：")
                for row in rows:
                    config_id, model_name = row
                    # 根据模型名称推断维度
                    default_dim = 1024  # 默认 1024
                    if 'v3' in model_name.lower() or '1536' in model_name.lower():
                        default_dim = 1536
                    elif 'v2' in model_name.lower() or '1024' in model_name.lower():
                        default_dim = 1024
                    
                    conn.execute(text(
                        f"UPDATE model_configs SET dimension = {default_dim} WHERE id = {config_id}"
                    ))
                    print(f"  - {model_name}: 设置维度为 {default_dim}")
                
                conn.commit()
                print("\n[OK] 现有 Embedding 模型维度已更新")
        
    except Exception as e:
        print(f"[ERROR] 添加列失败：{str(e)}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    add_dimension_column()
    print("\n数据库迁移完成！")
