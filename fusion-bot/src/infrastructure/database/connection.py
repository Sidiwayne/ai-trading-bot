"""
Database Connection Manager for FusionBot
==========================================

PostgreSQL connection management with SQLAlchemy.
"""

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from src.config import get_settings
from src.utils.logging import get_logger
from src.infrastructure.database.models import Base

logger = get_logger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions.
    
    Usage:
        db = DatabaseManager(database_url)
        db.init_db()  # Create tables
        
        with db.session() as session:
            # Use session
            ...
    """
    
    def __init__(self, database_url: str):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        
        # Create engine with connection pooling
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            echo=False,  # Set True for SQL debugging
        )
        
        # Session factory
        self._session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        
        logger.info("Database manager initialized", database_url=self._mask_url(database_url))
    
    def _mask_url(self, url: str) -> str:
        """Mask password in database URL for logging."""
        import re
        return re.sub(r':([^@]+)@', ':***@', url)
    
    def init_db(self) -> None:
        """
        Initialize database - create all tables.
        
        This is safe to call multiple times; it won't
        recreate existing tables.
        """
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables initialized successfully")
    
    def drop_all(self) -> None:
        """
        Drop all tables. USE WITH CAUTION!
        
        Only for testing/development.
        """
        logger.warning("Dropping all database tables!")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("All tables dropped")
    
    def health_check(self) -> bool:
        """
        Check database connectivity.
        
        Returns:
            True if database is accessible
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        
        Automatically commits on success, rolls back on error.
        
        Yields:
            SQLAlchemy Session
        
        Usage:
            with db.session() as session:
                session.add(record)
                # Auto-commits at end of block
        """
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Database session error, rolling back", error=str(e))
            raise
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """
        Get a new session (caller must manage lifecycle).
        
        Returns:
            SQLAlchemy Session
        
        Note:
            Prefer using the session() context manager instead.
        """
        return self._session_factory()
    
    def close(self) -> None:
        """Close all database connections."""
        self.engine.dispose()
        logger.info("Database connections closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Lazily initializes on first call.
    
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    
    if _db_manager is None:
        settings = get_settings()
        _db_manager = DatabaseManager(settings.database_url)
        _db_manager.init_db()
    
    return _db_manager


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Convenience function to get a database session.
    
    Yields:
        SQLAlchemy Session
    
    Usage:
        with get_session() as session:
            records = session.query(TradeORM).all()
    """
    db = get_db_manager()
    with db.session() as session:
        yield session

