from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import redis
import pika
import logging
import os

logger = logging.getLogger(__name__)

Base = declarative_base()

# Global connection objects
engine = None
SessionLocal = None
redis_client = None


def initialize_connections():
    """Initialize all connections"""
    global engine, SessionLocal, redis_client

    # Get credentials from environment
    db_user = os.getenv('POSTGRES_USER')
    db_password = os.getenv('POSTGRES_PASSWORD')
    db_name = os.getenv('POSTGRES_DB')
    db_host = os.getenv('POSTGRES_HOST', 'postgres')

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    redis_url = f"redis://:{os.getenv('REDIS_PASSWORD')}@redis:6379"

    # Initialize connections
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    redis_client = redis.from_url(redis_url)

    # Test connections
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        redis_client.ping()
        logger.info("✅ Database and Redis connections initialized successfully")
    except Exception as e:
        logger.error(f"❌ Connection initialization failed: {e}")
        raise


def get_db():
    """Database dependency for FastAPI"""
    if SessionLocal is None:
        initialize_connections()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis_connection():
    """Get Redis client"""
    if redis_client is None:
        initialize_connections()
    return redis_client


def get_rabbitmq_connection():
    """Get RabbitMQ connection"""
    # For now, return None since we're not using RabbitMQ yet
    return None, None


# Initialize connections on import
try:
    initialize_connections()
except Exception as e:
    logger.warning(f"Initial connection failed, will retry: {e}")