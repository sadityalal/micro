from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import redis
import os


class Database:
    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
        self.engine = None
        self.SessionLocal = None
        self.redis_client = None

    def initialize(self, database_url: str, redis_url: str):
        if self.engine is None:
            self.engine = create_engine(database_url)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.redis_client = redis.from_url(redis_url)

    @contextmanager
    def get_session(self):
        if self.engine is None:
            database_url = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/pavitra_db")
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            self.initialize(database_url, redis_url)

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_redis(self):
        if self.redis_client is None:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            self.redis_client = redis.from_url(redis_url)
        return self.redis_client


def get_db(tenant_id: int = 1):
    db = Database(tenant_id=tenant_id)
    with db.get_session() as session:
        yield session


def get_redis(tenant_id: int = 1):
    db = Database(tenant_id=tenant_id)
    return db.get_redis()


Base = declarative_base()