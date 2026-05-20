"""
数据库初始化脚本
================
创建数据库表并初始化默认管理员账户
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import engine, SessionLocal
from app.models import Base, User, UserRole
from app.core.security import get_password_hash
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def init_db():
    """创建所有数据库表"""
    logger.info("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")

    _migrate_message_table()


def _migrate_message_table():
    """迁移 messages 表：添加 confidence/features/token_usage 列"""
    try:
        with engine.connect() as conn:
            from sqlalchemy import text, inspect
            inspector = inspect(conn)
            existing_cols = {c["name"] for c in inspector.get_columns("messages")}

            if "confidence" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN confidence VARCHAR(20) DEFAULT NULL COMMENT '答案置信度'"))
                logger.info("数据库迁移: messages 表添加 confidence 列")
            if "features" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN features TEXT DEFAULT NULL COMMENT '功能状态(JSON)'"))
                logger.info("数据库迁移: messages 表添加 features 列")
            if "token_usage" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN token_usage TEXT DEFAULT NULL COMMENT 'Token使用详情(JSON)'"))
                logger.info("数据库迁移: messages 表添加 token_usage 列")
            conn.commit()
    except Exception as e:
        logger.warning(f"数据库迁移 (messages表) 失败（可安全忽略，已存在的表可能已包含这些列）: {e}")


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
            max_questions_per_day=9999,
            max_uploads_per_day=9999
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


if __name__ == "__main__":
    init_db()
    create_default_admin()
    print("\n数据库初始化完成！")
    print("警告：请立即登录并修改默认密码！")
    print("\n提示：如果需要清空向量库，请运行：python scripts/vector/clear_vector_store.py")
