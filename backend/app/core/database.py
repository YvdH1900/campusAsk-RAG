"""
数据库连接模块
=============
负责创建和管理数据库连接。
使用 SQLAlchemy ORM 框架，提供数据库会话和基类模型。
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


# ==================== 数据库引擎配置 ====================
# create_engine: 创建数据库引擎，负责管理连接池
# settings.DATABASE_URL: 从配置中读取数据库连接字符串
# pool_pre_ping=True: 每次从连接池获取连接前先测试连接是否有效
#   这样可以避免使用已断开的连接，提高稳定性
# connect_args: 设置连接参数（charset 确保中文正常显示）
# pool_recycle: 连接回收时间（秒），避免连接超时
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={"charset": "utf8mb4"},
    pool_recycle=3600,
    echo=False
)


# ==================== 数据库会话工厂 ====================
# sessionmaker: 创建会话工厂，用于生成数据库会话对象
# autocommit=False: 禁用自动提交，使用事务管理
# autoflush=False: 禁用自动刷新，手动控制何时将更改写入数据库
# bind=engine: 绑定到上面创建的数据库引擎
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ==================== ORM 基类 ====================
# declarative_base: 创建 ORM 模型的基类
# 所有数据库模型类都需要继承这个基类
# 它提供了表映射、字段定义等 ORM 功能
Base = declarative_base()


def get_db():
    """
    数据库会话依赖注入函数
    
    这是一个生成器函数，用于 FastAPI 的依赖注入系统。
    每次请求都会创建一个新的数据库会话，请求结束后自动关闭。
    
    使用方式:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    
    工作流程:
        1. 创建一个新的数据库会话
        2. 通过 yield 将会话提供给请求处理函数
        3. 无论请求是否成功，finally 块都会执行
        4. 关闭数据库会话，释放连接回连接池
    
    Yields:
        Session: SQLAlchemy 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
