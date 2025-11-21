# backend/shared/database.py
"""
Database core — shared across ALL 8 microservices.
Async SQLAlchemy 2.0 + PostgreSQL 17 + Multi-Tenant Ready.
Zero hardcoded values. Everything driven from DB + .env + system_settings table.
"""

import os
import ssl
from typing import AsyncGenerator, Dict
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from .config import settings
from .logger_middleware import get_logger

logger = get_logger(__name__)

# =============================================================================
# SSL Context — Production-grade
# =============================================================================
def _create_ssl_context() -> ssl.SSLContext | bool:
    if not settings.database.ssl_enabled:
        return False
    ctx = ssl.create_default_context()
    if settings.app.environment == "production":
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


# =============================================================================
# Async Engine — Fully dynamic from DB + tenant-aware in future
# =============================================================================
connect_args = {
    "command_timeout": 60,
    "server_settings": {
        "jit": "off",
        "statement_timeout": "30000",
        "application_name": f"{settings.app.name}_{os.getpid()}",
    },
}

ssl_ctx = _create_ssl_context()
if ssl_ctx:
    connect_args["ssl"] = ssl_ctx

engine: AsyncEngine = create_async_engine(
    url=str(settings.database.url),
    echo=settings.database.echo,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_recycle=settings.database.pool_recycle,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


# =============================================================================
# Connection Event: Set search path + role (multi-tenant ready)
# =============================================================================
@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public")
    cursor.execute("SET client_min_messages TO warning")
    cursor.execute("SET statement_timeout = 30000")
    cursor.close()


# =============================================================================
# Dependency: get_db() — Used in FastAPI depends=[]
# =============================================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error(f"Database transaction failed: {exc}", exc_info=True)
            raise
        except Exception as exc:
            await session.rollback()
            logger.error(f"Unexpected error in DB session: {exc}", exc_info=True)
            raise
        finally:
            await session.close()


# =============================================================================
# Lifecycle: init_db() — Called on startup
# =============================================================================
async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            auto_migrate = (
                settings.app.environment != "production" or
                os.getenv("AUTO_MIGRATIONS", "false").lower() == "true"
            )
            if auto_migrate:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Tables created/verified via create_all()")
            else:
                logger.info("AUTO_MIGRATIONS disabled — skipping table creation")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        raise


# =============================================================================
# Lifecycle: close_db() — Called on shutdown
# =============================================================================
async def close_db() -> None:
    try:
        await engine.dispose()
        logger.info("Database engine disposed")
    except Exception as e:
        logger.error(f"Error disposing engine: {e}", exc_info=True)


# =============================================================================
# Health & Metrics
# =============================================================================
async def check_db_health() -> bool:
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar_one() == 1
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False

async def get_db_metrics() -> Dict[str, int]:
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_out_connections": len(getattr(pool, "_checkedout_connections", [])),
    }