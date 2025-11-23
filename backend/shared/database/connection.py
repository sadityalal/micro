from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import redis
from typing import Generator
import threading
import os


class DatabaseManager:
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, tenant_id: int = 1):
        with cls._lock:
            if tenant_id not in cls._instances:
                instance = super().__new__(cls)
                instance.tenant_id = tenant_id
                instance.initialized = False
                cls._instances[tenant_id] = instance
            return cls._instances[tenant_id]

    def initialize(self, database_url: str = None, redis_url: str = None):
        """Initialize with URLs or use environment variables as fallback"""
        if not self.initialized:
            # Use provided URLs or fall back to environment variables
            db_url = database_url or os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/pavitra_db")
            redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")

            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False
            )
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            self.redis_pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=20,
                decode_responses=True
            )
            self.initialized = True

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        if not self.initialized:
            # Auto-initialize if not already done
            self.initialize()

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_redis(self) -> redis.Redis:
        if not self.initialized:
            # Auto-initialize if not already done
            self.initialize()
        return redis.Redis(connection_pool=self.redis_pool)


# Global database manager instance for default tenant
_default_db_manager = DatabaseManager(1)


def initialize_databases():
    """Explicitly initialize databases at application startup"""
    _default_db_manager.initialize()


def get_db(tenant_id: int = 1) -> Generator[Session, None, None]:
    db_manager = DatabaseManager(tenant_id)
    with db_manager.get_session() as session:
        yield session


def get_redis(tenant_id: int = 1) -> redis.Redis:
    db_manager = DatabaseManager(tenant_id)
    return db_manager.get_redis()


Base = declarative_base()