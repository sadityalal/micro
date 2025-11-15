import redis.asyncio as redis
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.engine.url import URL
import asyncio
import os
from .database import async_session
from .logger import get_logger

logger = get_logger(__name__)


class InfrastructureService:
    def __init__(self):
        self._redis_pools: Dict[str, redis.Redis] = {}
        self._db_engines: Dict[str, Any] = {}
        self._session_makers: Dict[str, Any] = {}
        self._cache_lock = asyncio.Lock()

    async def get_redis_client(self, tenant_id: int, purpose: str) -> redis.Redis:
        """
        Get Redis client for specific tenant and purpose from database configuration
        """
        cache_key = f"{tenant_id}:{purpose}"

        async with self._cache_lock:
            if cache_key in self._redis_pools:
                return self._redis_pools[cache_key]

            try:
                # Get Redis configuration from database
                async with async_session() as db:
                    result = await db.execute(
                        "SELECT host, port, database_name, username, password "
                        "FROM infrastructure_settings "
                        "WHERE tenant_id = :tid AND service_name = :service_name AND service_type = 'redis'",
                        {"tid": tenant_id, "service_name": f"{purpose}_redis"}
                    )
                    config = result.fetchone()

                    if not config:
                        # Fallback to environment-based configuration
                        redis_host = os.getenv(f"REDIS_{purpose.upper()}_HOST", "redis")
                        redis_port = int(os.getenv(f"REDIS_{purpose.upper()}_PORT", "6379"))
                        redis_db = int(os.getenv(f"REDIS_{purpose.upper()}_DB", "0" if purpose == "cache" else "1"))

                        config = type('Config', (), {
                            'host': redis_host,
                            'port': redis_port,
                            'database_name': str(redis_db),
                            'username': os.getenv(f"REDIS_{purpose.upper()}_USERNAME", ""),
                            'password': os.getenv(f"REDIS_{purpose.upper()}_PASSWORD", "")
                        })()

                    # Create Redis connection
                    redis_client = redis.Redis(
                        host=config.host,
                        port=config.port,
                        db=int(config.database_name) if config.database_name else 0,
                        username=config.username if config.username else None,
                        password=config.password if config.password else None,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True
                    )

                    # Test connection
                    await redis_client.ping()

                    self._redis_pools[cache_key] = redis_client
                    logger.info(f"Redis client created for tenant {tenant_id}, purpose {purpose}")
                    return redis_client

            except Exception as e:
                logger.error(f"Failed to create Redis client for tenant {tenant_id}, purpose {purpose}: {e}")
                raise

    async def get_db_session(self, tenant_id: int = None) -> AsyncSession:
        """
        Get database session for the specified tenant
        If no tenant_id provided, uses the default database
        """
        if not tenant_id:
            # Return default session
            return async_session()

        cache_key = f"db_{tenant_id}"

        async with self._cache_lock:
            if cache_key in self._session_makers:
                session_maker = self._session_makers[cache_key]
                return session_maker()

            try:
                # Get database configuration from infrastructure_settings
                async with async_session() as db:
                    result = await db.execute(
                        "SELECT host, port, username, password, database_name, connection_string "
                        "FROM infrastructure_settings "
                        "WHERE tenant_id = :tid AND service_type = 'postgresql' AND service_name = 'main_database'",
                        {"tid": tenant_id}
                    )
                    config = result.fetchone()

                    if not config:
                        # Fallback to default database
                        return async_session()

                    # Build connection URL
                    if config.connection_string:
                        db_url = config.connection_string
                    else:
                        db_url = URL.create(
                            drivername="postgresql+asyncpg",
                            username=config.username,
                            password=config.password,
                            host=config.host,
                            port=config.port,
                            database=config.database_name
                        )

                    # Create async engine
                    engine = create_async_engine(
                        db_url,
                        pool_size=getattr(config, 'max_connections', 20),
                        max_overflow=30,
                        pool_pre_ping=True,
                        echo=False
                    )

                    # Create session maker
                    session_maker = async_sessionmaker(
                        engine,
                        class_=AsyncSession,
                        expire_on_commit=False
                    )

                    self._session_makers[cache_key] = session_maker
                    self._db_engines[cache_key] = engine

                    logger.info(f"Database session maker created for tenant {tenant_id}")
                    return session_maker()

            except Exception as e:
                logger.error(f"Failed to create database session for tenant {tenant_id}: {e}")
                # Fallback to default session
                return async_session()

    async def close_connections(self):
        """Close all connections"""
        try:
            # Close Redis connections
            for redis_client in self._redis_pools.values():
                await redis_client.close()
            self._redis_pools.clear()

            # Close database engines
            for engine in self._db_engines.values():
                await engine.dispose()
            self._db_engines.clear()
            self._session_makers.clear()

            logger.info("All infrastructure connections closed")
        except Exception as e:
            logger.error(f"Error closing infrastructure connections: {e}")


# Global instance
infra_service = InfrastructureService()