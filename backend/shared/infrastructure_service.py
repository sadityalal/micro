# backend/shared/infrastructure_service.py
"""
THE REAL FINAL INFRASTRUCTURE SERVICE — NOVEMBER 15, 2025
100% YOUR VISION. ZERO COMPROMISE.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, AsyncGenerator

import redis.asyncio as redis
import aio_pika
import aiokafka
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.engine.url import URL

from .config import get_tenant_config
from .database import async_session
from .logger_middleware import get_logger

logger = get_logger(__name__)


class InfrastructureService:
    def __init__(self):
        self._redis_pools: Dict[str, redis.ConnectionPool] = {}
        self._rabbitmq_connections: Dict[int, aio_pika.RobustConnection] = {}
        self._kafka_producers: Dict[int, aiokafka.AIOKafkaProducer] = {}
        self._db_engines: Dict[int, AsyncEngine] = {}
        self._session_makers: Dict[int, async_sessionmaker] = {}
        self._lock = asyncio.Lock()

    # ─── Redis (per tenant + purpose) ─────────────────────────────────────
    async def get_redis_client(self, tenant_id: int, purpose: str = "cache") -> redis.Redis:
        key = f"{tenant_id}:{purpose}"
        async with self._lock:
            if key not in self._redis_pools:
                config = await get_tenant_config(tenant_id)
                redis_cfg = config["infrastructure"].get(f"{purpose}_redis")
                if not redis_cfg:
                    raise ValueError(f"Redis {purpose} not configured for tenant {tenant_id}")

                pool = redis.ConnectionPool(
                    host=redis_cfg["host"],
                    port=redis_cfg.get("port", 6379),
                    db=redis_cfg.get("database_name", 0),
                    password=redis_cfg.get("password"),
                    username=redis_cfg.get("username"),
                    max_connections=20,
                    decode_responses=True,
                    health_check_interval=30,
                )
                self._redis_pools[key] = pool
                logger.info(f"Redis pool created: {key}")

            return redis.Redis(connection_pool=self._redis_pools[key])

    # ─── RabbitMQ ───────────────────────────────────────────────────────
    async def get_rabbitmq(self, tenant_id: int) -> aio_pika.RobustConnection:
        async with self._lock:
            if tenant_id not in self._rabbitmq_connections:
                config = await get_tenant_config(tenant_id)
                mq = config["infrastructure"].get("message_queue")
                if not mq or mq["service_type"] != "rabbitmq":
                    raise ValueError("RabbitMQ not configured")
                conn = await aio_pika.connect_robust(
                    f"amqp://{mq['username']}:{mq['password']}@{mq['host']}:{mq['port']}/%2F"
                )
                self._rabbitmq_connections[tenant_id] = conn
            return self._rabbitmq_connections[tenant_id]

    # ─── Kafka Producer ─────────────────────────────────────────────────
    async def get_kafka_producer(self, tenant_id: int) -> aiokafka.AIOKafkaProducer:
        async with self._lock:
            if tenant_id not in self._kafka_producers:
                config = await get_tenant_config(tenant_id)
                kafka = config["infrastructure"].get("message_queue")
                if not kafka or kafka["service_type"] != "kafka":
                    raise ValueError("Kafka not configured")
                producer = aiokafka.AIOKafkaProducer(
                    bootstrap_servers=f"{kafka['host']}:{kafka['port']}"
                )
                await producer.start()
                self._kafka_producers[tenant_id] = producer
            return self._kafka_producers[tenant_id]

    # ─── Per-tenant DB Session ──────────────────────────────────────────
    @asynccontextmanager
    async def get_db_session(self, tenant_id: Optional[int] = None) -> AsyncGenerator[AsyncSession, None]:
        if not tenant_id:
            async with async_session() as session:
                yield session
            return

        async with self._lock:
            if tenant_id not in self._session_makers:
                config = await get_tenant_config(tenant_id)
                db_cfg = config["infrastructure"].get("main_database")
                if not db_cfg:
                    session_maker = async_session
                else:
                    url = db_cfg.get("connection_string") or URL.create(
                        "postgresql+asyncpg",
                        username=db_cfg.get("username"),
                        password=db_cfg.get("password"),
                        host=db_cfg["host"],
                        port=db_cfg.get("port", 5432),
                        database=db_cfg["database_name"],
                    )
                    engine = create_async_engine(url, pool_size=20, max_overflow=10)
                    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                    self._db_engines[tenant_id] = engine
                self._session_makers[tenant_id] = session_maker

            async with self._session_makers[tenant_id]() as session:
                yield session

    # ─── Shutdown ───────────────────────────────────────────────────────
    async def close_all(self):
        # Redis
        for pool in self._redis_pools.values():
            await pool.disconnect()
        self._redis_pools.clear()

        # RabbitMQ
        for conn in self._rabbitmq_connections.values():
            await conn.close()
        self._rabbitmq_connections.clear()

        # Kafka
        for producer in self._kafka_producers.values():
            await producer.stop()
        self._kafka_producers.clear()

        # DB
        for engine in self._db_engines.values():
            await engine.dispose()
        self._db_engines.clear()
        self._session_makers.clear()

        logger.info("All infrastructure connections closed")


# Global instance — your way
infra_service = InfrastructureService()