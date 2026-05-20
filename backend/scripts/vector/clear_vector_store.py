"""
清空向量库脚本
================
删除 Milvus 向量库中的所有数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.vector_store import VectorStore
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def clear_vector_store():
    """清空向量库"""
    logger.info("正在清空向量库...")
    
    try:
        vector_store = VectorStore()
        
        # 删除集合
        vector_store.drop_collection()
        
        logger.info("向量库已清空")
        print("向量库已清空")
        
    except Exception as e:
        logger.error(f"清空向量库失败：{str(e)}")
        print(f"清空向量库失败：{str(e)}")
        raise


if __name__ == "__main__":
    clear_vector_store()
