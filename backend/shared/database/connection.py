import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import redis


class Database:
    def __init__(self):
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://admin:admin123@localhost:5432/pavitra_db"
        )
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Redis connection for sessions/rate limiting
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = redis.from_url(self.redis_url)

    @contextmanager
    def get_session(self):
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
        return self.redis_client


# Global database instance
db = Database()


def get_db():
    with db.get_session() as session:
        yield session


def get_redis():
    return db.get_redis()