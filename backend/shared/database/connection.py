from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import redis
from typing import Generator
import threading


class DatabaseManager:
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, tenant_id: int = 1):
        with cls._lock:
            if tenant_id not in cls._instances:
                instance = super().__new__(cls)
                instance.initialized = False
                cls._instances[tenant_id] = instance
            return cls._instances[tenant_id]

    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
        if not hasattr(self, 'initialized'):
            self.initialized = False

    def initialize(self, database_url: str, redis_url: str):
        if not self.initialized:
            self.engine = create_engine(
                database_url,
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
            raise RuntimeError("Database not initialized. Call initialize() first.")

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
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return redis.Redis(connection_pool=self.redis_pool)


def get_db(tenant_id: int = 1) -> Generator[Session, None, None]:
    db_manager = DatabaseManager(tenant_id)
    with db_manager.get_session() as session:
        yield session


def get_redis(tenant_id: int = 1) -> redis.Redis:
    db_manager = DatabaseManager(tenant_id)
    return db_manager.get_redis()


Base = declarative_base()