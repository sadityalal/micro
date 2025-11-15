import os
from typing import Dict, Any, Optional
from pydantic import BaseSettings
import json


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "postgresql+asyncpg://root:root123@localhost:5432/pavitra_db"

    # Redis
    redis_cache_host: str = "redis"
    redis_cache_port: int = 6379
    redis_cache_db: int = 0

    redis_session_host: str = "redis"
    redis_session_port: int = 6379
    redis_session_db: int = 1

    redis_rate_limit_host: str = "redis"
    redis_rate_limit_port: int = 6379
    redis_rate_limit_db: int = 2

    # JWT
    jwt_secret_key: str = "your-super-secure-jwt-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expiry_minutes: int = 30

    # Application
    app_name: str = "Pavitra E-Commerce"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Security
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


async def get_tenant_settings(tenant_id: int) -> Dict[str, Any]:
    """
    Get tenant-specific settings from database
    """
    from .database import async_session

    async with async_session() as db:
        try:
            # Get security settings
            result = await db.execute(
                "SELECT jwt_secret_key, jwt_algorithm, access_token_expiry_minutes, cors_origins "
                "FROM security_settings WHERE tenant_id = :tid",
                {"tid": tenant_id}
            )
            security_settings = result.fetchone()

            # Get system settings
            result = await db.execute(
                "SELECT setting_key, setting_value, setting_type "
                "FROM tenant_system_settings WHERE tenant_id = :tid",
                {"tid": tenant_id}
            )
            system_settings = {row.setting_key: row.setting_value for row in result.fetchall()}

            return {
                "security": security_settings._asdict() if security_settings else {},
                "system": system_settings
            }

        except Exception as e:
            from .logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"Failed to get tenant settings for {tenant_id}: {e}")
            return {}