"""
数据库连接和会话管理
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: str = None):
        """
        初始化数据库连接
        
        Args:
            database_url: 数据库连接 URL，例如：
                - PostgreSQL: postgresql://user:pass@localhost:5432/sre_db
                - SQLite (测试): sqlite:///./sre_test.db
        """
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql://postgres:postgres@localhost:5432/sre_db'
        )
        
        # 创建引擎
        self.engine = create_engine(
            self.database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,  # 连接前检查
            echo=os.getenv('SQL_ECHO', 'false').lower() == 'true'
        )
        
        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def get_session(self) -> Generator[Session, None, None]:
        """
        获取数据库会话
        
        Usage:
            db = DatabaseManager()
            with db.get_session() as session:
                # 使用 session
        """
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def init_db(self):
        """初始化数据库（创建所有表）"""
        from models.database import Base
        Base.metadata.create_all(bind=self.engine)
    
    def drop_db(self):
        """删除所有表（仅用于测试）"""
        from models.database import Base
        Base.metadata.drop_all(bind=self.engine)


# 全局数据库实例
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_session() -> Generator[Session, None, None]:
    """
    获取数据库会话（用于 FastAPI Depends）
    
    Usage:
        @router.get("/")
        def handler(session: Session = Depends(get_session)):
            ...
    """
    db_manager = get_db_manager()
    yield from db_manager.get_session()
