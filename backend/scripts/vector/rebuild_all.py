"""
完整初始化脚本
================
重建数据库并清空向量库
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import engine, SessionLocal
from app.models import Base, User, UserRole
from app.core.security import get_password_hash
from app.services.vector_store import VectorStore
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def drop_all_tables():
    """删除所有数据库表"""
    logger.info("正在删除所有数据库表...")
    Base.metadata.drop_all(bind=engine)
    logger.info("所有数据库表已删除")


def init_db():
    """创建所有数据库表"""
    logger.info("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")


def create_default_admin():
    """创建默认管理员账户"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            logger.info("管理员账户已存在")
            return
        
        # 从环境变量获取管理员密码，如果没有设置则使用默认密码
        admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD")
        if not admin_password:
            import secrets
            admin_password = secrets.token_urlsafe(12)
        
        admin = User(
            username="admin",
            email="admin@campus.com",
            hashed_password=get_password_hash(admin_password),
            role=UserRole.ADMIN,
            is_active=True,
            # 管理员无限制，这些字段仅用于兼容性保留
        )
        db.add(admin)
        db.commit()
        
        # 只在开发环境打印密码，生产环境记录到日志文件
        if os.environ.get("ENVIRONMENT") == "development":
            logger.info("默认管理员账户创建成功")
            print("管理员账户已创建，密码已通过环境变量设置")
            print("警告：请立即登录并修改密码！")
        else:
            logger.info("默认管理员账户创建成功")
            print("默认管理员账户已创建")
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建管理员账户失败：{e}")
        raise
    finally:
        db.close()


def clear_vector_store():
    """清空向量库"""
    logger.info("正在清空向量库...")
    
    try:
        vector_store = VectorStore()
        vector_store.drop_collection()
        
        logger.info("向量库已清空")
        print("向量库已清空")
        
    except Exception as e:
        logger.error(f"清空向量库失败：{str(e)}")
        print(f"清空向量库失败：{str(e)}")
        raise


if __name__ == "__main__":
    print("=" * 50)
    print("完整初始化 - 数据库 + 向量库")
    print("=" * 50)
    
    print("\n步骤 1/4: 删除所有数据库表...")
    drop_all_tables()
    
    print("\n步骤 2/4: 创建数据库表...")
    init_db()
    
    print("\n步骤 3/4: 创建管理员账号...")
    create_default_admin()
    
    print("\n步骤 4/4: 清空向量库...")
    clear_vector_store()
    
    print("\n" + "=" * 50)
    print("初始化完成！")
    print("=" * 50)
    print("\n警告：请立即登录并修改默认密码！")
