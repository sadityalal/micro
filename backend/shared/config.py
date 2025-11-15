# backend/shared/config.py
"""
Configuration system — THE BRAIN of the entire platform.

RULE: 
- .env → ONLY for initial DB connection (bootstrap)
- Everything else → FROM DATABASE (per-tenant, dynamic, auditable)

This file is imported by ALL 8 microservices.
"""

import os
from typing import Dict, Any, Optional
from functools import lru_cache
from pydantic import BaseSettings, Field, validator
from sqlalchemy import text

from .database import async_session
from .logger_middleware import get_logger

logger = get_logger(__name__)


# =============================================================================
# 1. Bootstrap Settings — ONLY from .env / system env
#    This is the ONLY place we read environment variables.
# =============================================================================
class BootstrapSettings(BaseSettings):
    # Required: How to reach PostgreSQL on first startup
    database_url: str = Field(..., env="DATABASE_URL")

    # Optional overrides (rarely used)
    app_name: str = Field("Pavitra Platform", env="APP_NAME")
    environment: str = Field("production", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton — loaded once at import time
bootstrap = BootstrapSettings()
settings = bootstrap  # backward compatible alias


# =============================================================================
# 2. Tenant Settings Cache + Dynamic Loader
#    All real config comes from here — per tenant, from DB
# =============================================================================
@lru_cache(maxsize=128)
async def get_tenant_config(tenant_id: int) -> Dict[str, Any]:
    """
    Get COMPLETE runtime configuration for a tenant.
    Cached aggressively — settings rarely change.
    """
    if tenant_id <= 0:
        logger.warning(f"Invalid tenant_id: {tenant_id}")
        return {}

    async with async_session() as db:
        try:
            # 1. Security Settings (JWT, tokens, etc.)
            sec_result = await db.execute(
                text("""
                    SELECT 
                        jwt_secret_key, jwt_algorithm,
                        access_token_expiry_minutes, refresh_token_expiry_days,
                        password_reset_expiry_minutes, require_https,
                        max_login_attempts, account_lockout_minutes
                    FROM security_settings 
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            )
            security = sec_result.fetchone()

            # 2. Session Settings
            sess_result = await db.execute(
                text("""
                    SELECT storage_type, timeout_type, session_timeout_minutes,
                           absolute_timeout_minutes, sliding_timeout_minutes,
                           max_concurrent_sessions, secure_cookies
                    FROM session_settings 
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            )
            session = sess_result.fetchone()

            # 3. Rate Limit Settings
            rl_result = await db.execute(
                text("""
                    SELECT strategy, requests_per_minute, requests_per_hour,
                           requests_per_day, burst_capacity, enabled
                    FROM rate_limit_settings 
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            )
            rate_limit = rl_result.fetchone()

            # 4. Infrastructure Services (Redis, RabbitMQ, etc.)
            infra_result = await db.execute(
                text("""
                    SELECT service_name, service_type, host, port, username, 
                           password, database_name, connection_string, status
                    FROM infrastructure_settings 
                    WHERE tenant_id = :tid AND status = 'active'
                """),
                {"tid": tenant_id}
            )
            infra_rows = infra_result.fetchall()
            infrastructure = {
                row.service_name: row._asdict() for row in infra_rows
            }

            # 5. Service URLs (internal + external APIs)
            urls_result = await db.execute(
                text("""
                    SELECT service_name, base_url, health_endpoint, status
                    FROM service_urls 
                    WHERE tenant_id = :tid AND status = 'active'
                """),
                {"tid": tenant_id}
            )
            service_urls = {
                row.service_name: row._asdict() for row in urls_result.fetchall()
            }

            # 6. Generic tenant settings (key-value)
            sys_result = await db.execute(
                text("SELECT setting_key, setting_value FROM tenant_system_settings WHERE tenant_id = :tid"),
                {"tid": tenant_id}
            )
            system_settings = {row.setting_key: row.setting_value for row in sys_result.fetchall()}

            # Return complete config object
            config = {
                "security": security._asdict() if security else {},
                "session": session._asdict() if session else {},
                "rate_limit": rate_limit._asdict() if rate_limit else {},
                "infrastructure": infrastructure,
                "service_urls": service_urls,
                "system": system_settings,
            }

            logger.debug(f"Tenant {tenant_id} config loaded and cached")
            return config

        except Exception as e:
            logger.error(f"Failed to load config for tenant {tenant_id}: {e}", exc_info=True)
            return {}


# =============================================================================
# 3. Convenience Helpers
# =============================================================================
async def get_jwt_secret(tenant_id: int) -> Optional[str]:
    config = await get_tenant_config(tenant_id)
    return config.get("security", {}).get("jwt_secret_key")


async def get_redis_config(tenant_id: int, service_name: str = "cache_redis") -> Optional[Dict]:
    config = await get_tenant_config(tenant_id)
    return config.get("infrastructure", {}).get(service_name)


async def get_system_setting(key: str, default: Any = None) -> Any:
    # Global system settings (not tenant-specific)
    # You can add a system_settings cache later
    return default


# Clear cache (e.g. after admin updates settings)
def clear_tenant_config_cache(tenant_id: Optional[int] = None):
    if tenant_id:
        get_tenant_config.cache_clear()  # SQLAlchemy 2.0+ supports this
        logger.info(f"Config cache cleared for tenant {tenant_id}")
    else:
        get_tenant_config.cache_clear()


# Export for backward compatibility
get_tenant_settings = get_tenant_config