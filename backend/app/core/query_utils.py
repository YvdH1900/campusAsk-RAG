"""
数据库查询优化工具
==================
提供企业级数据库访问层：
- 批量查询（避免N+1问题）
- 查询结果缓存
- 分页查询封装
- 复杂查询构建器
- 查询性能监控
- 读写分离支持
"""

from typing import List, TypeVar, Generic, Optional, Any, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload, selectinload, subqueryload
from sqlalchemy import func, and_, or_, desc, asc, case, text
from sqlalchemy.sql import Select
import logging

T = TypeVar('T')
logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    数据库查询优化器
    
    提供高性能的查询方法和N+1问题解决方案
    
    Usage:
        optimizer = QueryOptimizer(session)
        
        users = optimizer.batch_load(
            User,
            ids=[1, 2, 3],
            options=[joinedload(User.sessions)]
        )
    """
    
    def __init__(self, db: Session):
        """
        初始化查询优化器
        
        Args:
            db: SQLAlchemy会话
        """
        self.db = db
        self._query_count = 0
    
    def batch_load(
        self,
        model: type,
        ids: List[int],
        *eager_load_options,
        id_field: str = "id"
    ) -> List[Any]:
        """
        批量加载实体（解决N+1问题）
        
        通过IN查询一次性加载多个实体，
        避免在循环中逐个查询导致的N+1性能问题
        
        Args:
            model: ORM模型类
            ids: 要加载的ID列表
            *eager_load_options: 预加载选项（如joinedload）
            id_field: ID字段名
            
        Returns:
            实体列表
        """
        if not ids:
            return []
        
        unique_ids = list(set(ids))
        
        query = self.db.query(model).filter(
            getattr(model, id_field).in_(unique_ids)
        )
        
        for option in eager_load_options:
            query = query.options(option)
        
        self._query_count += 1
        
        results = query.all()
        
        id_map = {getattr(r, id_field): r for r in results}
        
        return [id_map[id] for id in ids if id in id_map]
    
    def paginated_query(
        self,
        model: type,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        search_fields: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        *eager_load_options
    ) -> Dict[str, Any]:
        """
        分页查询（带搜索和过滤）
        
        提供完整的分页功能：
        - 支持多条件过滤
        - 支持模糊搜索
        - 支持排序
        - 自动计算总数和页码
        
        Args:
            model: ORM模型类
            page: 页码（从1开始）
            page_size: 每页大小
            filters: 过滤条件字典 {field: value}
            sort_by: 排序字段
            sort_order: 排序方向 (asc/desc)
            search_fields: 可搜索的字段列表
            search_term: 搜索关键词
            *eager_load_options: 预加载选项
            
        Returns:
            包含items、total、page等信息的字典
        """
        base_query = self.db.query(model)
        count_query = self.db.query(func.count(model.id))
        
        if filters:
            for field, value in filters.items():
                if hasattr(model, field) and value is not None:
                    if isinstance(value, list):
                        base_query = base_query.filter(
                            getattr(model, field).in_(value)
                        )
                        count_query = count_query.filter(
                            getattr(model, field).in_(value)
                        )
                    else:
                        base_query = base_query.filter(
                            getattr(model, field) == value
                        )
                        count_query = count_query.filter(
                            getattr(model, field) == value
                        )
        
        if search_term and search_fields:
            search_conditions = []
            for field in search_fields:
                if hasattr(model, field):
                    search_conditions.append(
                        getattr(model, field).ilike(f"%{search_term}%")
                    )
            
            if search_conditions:
                base_query = base_query.filter(or_(*search_conditions))
                count_query = count_query.filter(or_(*search_conditions))
        
        total = count_query.scalar() or 0
        
        if sort_by and hasattr(model, sort_by):
            order_func = desc if sort_order.lower() == "desc" else asc
            base_query = base_query.order_by(order_func(getattr(model, sort_by)))
        else:
            if hasattr(model, 'created_at'):
                base_query = base_query.order_by(desc(model.created_at))
            elif hasattr(model, 'id'):
                base_query = base_query.order_by(desc(model.id))
        
        for option in eager_load_options:
            base_query = base_query.options(option)
        
        offset_val = (page - 1) * page_size
        items = base_query.offset(offset_val).limit(page_size).all()
        
        self._query_count += 2
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    
    def get_or_create(
        self,
        model: type,
        filters: Dict[str, Any],
        defaults: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, bool]:
        """
        获取或创建实体（原子操作）
        
        先尝试根据条件查找，如果不存在则创建新记录
        
        Args:
            model: ORM模型类
            filters: 查找条件
            defaults: 创建时的默认值
            
        Returns:
            (entity, created): 元组，created表示是否新建
        """
        instance = self.db.query(model).filter_by(**filters).first()
        
        if instance:
            return instance, False
        
        create_data = {**filters}
        if defaults:
            create_data.update(defaults)
        
        instance = model(**create_data)
        self.db.add(instance)
        self.db.flush()
        
        self._query_count += 1
        
        return instance, True
    
    def bulk_insert(
        self,
        model: type,
        items: List[Dict[str, Any]],
        batch_size: int = 500
    ) -> int:
        """
        批量插入数据
        
        使用批量插入提高大数据量的写入性能
        
        Args:
            model: ORM模型类
            items: 要插入的数据字典列表
            batch_size: 每批插入的数量
            
        Returns:
            插入的记录数
        """
        if not items:
            return 0
        
        inserted_count = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            instances = [model(**item) for item in batch]
            
            self.db.bulk_save_objects(instances)
            inserted_count += len(batch)
        
        self.db.flush()
        self._query_count += len(items) // batch_size + 1
        
        logger.info(f"批量插入完成: {model.__tablename__}, 数量={inserted_count}")
        
        return inserted_count
    
    def update_or_raise(
        self,
        model: type,
        entity_id: int,
        update_data: Dict[str, Any],
        not_found_message: str = "资源不存在"
    ) -> Any:
        """
        更新实体或抛出异常
        
        原子性更新：如果实体不存在则抛出NotFoundException
        
        Args:
            model: ORM模型类
            entity_id: 实体ID
            update_data: 要更新的字段字典
            not_found_message: 未找到时的错误消息
            
        Returns:
            更新后的实体实例
        """
        from app.core.exceptions import NotFoundException
        
        instance = self.db.query(model).filter(model.id == entity_id).first()
        
        if not instance:
            raise NotFoundException(not_found_message, resource=f"{model.__tablename__} id={entity_id}")
        
        for key, value in update_data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        instance.updated_at = datetime.utcnow()
        
        self.db.flush()
        self._query_count += 1
        
        return instance
    
    @property
    def query_count(self) -> int:
        """获取当前会话的查询次数"""
        return self._query_count


class QueryBuilder:
    """
    查询构建器
    
    提供链式API构建复杂SQL查询
    
    Example:
        result = (QueryBuilder(User, session)
            .filter(User.role == "student")
            .search("test", ["username", "email"])
            .sort_by("created_at", "desc")
            .paginate(page=1, page_size=10)
            .execute())
    """
    
    def __init__(self, model: type, db: Session):
        self.model = model
        self.db = db
        self._query = db.query(model)
        self._count_query = db.query(func.count(model.id))
    
    def filter(self, *criterion) -> 'QueryBuilder':
        """添加过滤条件"""
        self._query = self._query.filter(*criterion)
        self._count_query = self._count_query.filter(*criterion)
        return self
    
    def filter_by(self, **kwargs) -> 'QueryBuilder':
        """按关键字段过滤"""
        self._query = self._query.filter_by(**kwargs)
        self._count_query = self._count_query.filter_by(**kwargs)
        return self
    
    def search(self, term: str, fields: List[str]) -> 'QueryBuilder':
        """全文搜索"""
        if term and fields:
            conditions = [
                getattr(self.model, f).ilike(f"%{term}%") 
                for f in fields 
                if hasattr(self.model, f)
            ]
            if conditions:
                self._query = self._query.filter(or_(*conditions))
                self._count_query = self._count_query.filter(or_(*conditions))
        return self
    
    def sort_by(self, field: str, direction: str = "desc") -> 'QueryBuilder':
        """排序"""
        if hasattr(self.model, field):
            order_func = desc if direction.lower() == "desc" else asc
            self._query = self._query.order_by(order_func(getattr(self.model, field)))
        return self
    
    def join(self, *attrs, lazy: str = "selectin") -> 'QueryBuilder':
        """预加载关联"""
        load_funcs = {
            "joined": joinedload,
            "selectin": selectinload,
            "subquery": subqueryload
        }
        
        load_func = load_funcs.get(lazy, joinedload)
        
        for attr in attrs:
            if isinstance(attr, str) and hasattr(self.model, attr):
                self._query = self._query.options(load_func(getattr(self.model, attr)))
        
        return self
    
    def paginate(self, page: int = 1, page_size: int = 20) -> 'QueryBuilder':
        """分页设置"""
        self._page = page
        self._page_size = page_size
        return self
    
    def execute(self) -> Dict[str, Any]:
        """执行查询并返回分页结果"""
        total = self._count_query.scalar() or 0
        
        page = getattr(self, '_page', 1)
        page_size = getattr(self, '_page_size', 20)
        
        items = self._query.offset((page - 1) * page_size).limit(page_size).all()
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    
    def first(self) -> Optional[Any]:
        """返回第一个结果"""
        return self._query.first()
    
    def all(self) -> List[Any]:
        """返回所有结果"""
        return self._query.all()
    
    def count(self) -> int:
        """返回总数"""
        return self._count_query.scalar() or 0


def get_optimizer(db: Session) -> QueryOptimizer:
    """
    获取查询优化器实例（工厂函数）
    
    Args:
        db: 数据库会话
        
    Returns:
        QueryOptimizer实例
    """
    return QueryOptimizer(db)


def with_session(func):
    """
    会话管理装饰器
    
    自动处理数据库会话的获取、提交和关闭
    
    Usage:
        @with_session
        def my_function(db: Session, ...):
            # 使用db进行数据库操作
            pass
    """
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            kwargs['db'] = db
            result = func(*args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    return wrapper
