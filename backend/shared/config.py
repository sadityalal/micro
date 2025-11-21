import os
from typing import Dict, Any, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from .logger_middleware import get_logger

logger = get_logger(__name__)


class BootstrapSettings(BaseSettings):
    database_url: str = Field(
        default=...,
        description="PostgreSQL database URL for configuration storage",
        env="DATABASE_URL"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }


# Only DATABASE_URL comes from environment
bootstrap = BootstrapSettings()
settings = bootstrap


@lru_cache(maxsize=128)
async def get_tenant_config(tenant_id: int) -> Dict[str, Any]:
    """
    Get ALL tenant configuration from database - no environment fallbacks
    """
    if tenant_id <= 0:
        logger.error(f"Invalid tenant_id: {tenant_id}")
        raise ValueError(f"Invalid tenant_id: {tenant_id}")

    try:
        # Import here to avoid circular imports
        from sqlalchemy import text
        from .database import async_session

        async with async_session() as db:
            # Security settings - JWT secrets etc.
            sec_result = await db.execute(
                text("""
                    SELECT
                        jwt_secret_key, jwt_algorithm,
                        access_token_expiry_minutes, refresh_token_expiry_days,
                        password_reset_expiry_minutes, require_https,
                        max_login_attempts, account_lockout_minutes,
                        cors_origins
                    FROM security_settings
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            )
            security = sec_result.fetchone()
            if not security:
                logger.error(f"No security settings found for tenant {tenant_id}")
                raise ValueError(f"Security configuration missing for tenant {tenant_id}")

            # Session settings
            sess_result = await db.execute(
                text("""
                    SELECT storage_type, timeout_type, session_timeout_minutes,
                           absolute_timeout_minutes, sliding_timeout_minutes,
                           max_concurrent_sessions, secure_cookies,
                           http_only_cookies, same_site_policy, cookie_domain,
                           cookie_path, enable_session_cleanup, cleanup_interval_minutes
                    FROM session_settings
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            )
            session = sess_result.fetchone()
            if not session:
                logger.error(f"No session settings found for tenant {tenant_id}")
                raise ValueError(f"Session configuration missing for tenant {tenant_id}")

            # Rate limit settings
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
            if not rate_limit:
                logger.error(f"No rate limit settings found for tenant {tenant_id}")
                raise ValueError(f"Rate limit configuration missing for tenant {tenant_id}")

            # Logging settings
            log_result = await db.execute(
                text("""
                    SELECT log_level, enable_audit_log, enable_access_log, 
                           enable_security_log, retention_days
                    FROM logging_settings
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            )
            logging_config = log_result.fetchone()
            if not logging_config:
                logger.error(f"No logging settings found for tenant {tenant_id}")
                raise ValueError(f"Logging configuration missing for tenant {tenant_id}")

            # Infrastructure settings - Redis, RabbitMQ etc.
            infra_result = await db.execute(
                text("""
                    SELECT service_name, service_type, host, port, username,
                           password, database_name, connection_string, status,
                           max_connections, timeout_seconds, health_check_url
                    FROM infrastructure_settings
                    WHERE tenant_id = :tid AND status = 'active'
                """),
                {"tid": tenant_id}
            )
            infra_rows = infra_result.fetchall()
            infrastructure = {
                row.service_name: dict(row._mapping) for row in infra_rows
            }

            # Service URLs
            urls_result = await db.execute(
                text("""
                    SELECT service_name, base_url, health_endpoint, status,
                           timeout_ms, retry_attempts, circuit_breaker_enabled
                    FROM service_urls
                    WHERE tenant_id = :tid AND status = 'active'
                """),
                {"tid": tenant_id}
            )
            service_urls = {
                row.service_name: dict(row._mapping) for row in urls_result.fetchall()
            }

            # System settings
            sys_result = await db.execute(
                text("SELECT setting_key, setting_value FROM tenant_system_settings WHERE tenant_id = :tid"),
                {"tid": tenant_id}
            )
            system_settings = {row.setting_key: row.setting_value for row in sys_result.fetchall()}

            config = {
                "security": dict(security._mapping),
                "session": dict(session._mapping),
                "rate_limit": dict(rate_limit._mapping),
                "logging": dict(logging_config._mapping),
                "infrastructure": infrastructure,
                "service_urls": service_urls,
                "system": system_settings,
            }

            logger.info(f"Tenant {tenant_id} configuration loaded from database")
            return config

    except Exception as e:
        logger.critical(f"Failed to load configuration from database for tenant {tenant_id}: {e}")
        raise


async def get_jwt_secret(tenant_id: int) -> str:
    """Get JWT secret ONLY from database"""
    config = await get_tenant_config(tenant_id)
    secret = config.get("security", {}).get("jwt_secret_key")
    if not secret:
        raise ValueError(f"JWT secret not configured for tenant {tenant_id}")
    return secret


async def get_redis_config(tenant_id: int, service_name: str = "cache_redis") -> Dict[str, Any]:
    """Get Redis config ONLY from database"""
    config = await get_tenant_config(tenant_id)
    redis_config = config.get("infrastructure", {}).get(service_name)
    if not redis_config:
        raise ValueError(f"Redis configuration '{service_name}' not found for tenant {tenant_id}")
    return redis_config


async def get_log_level(tenant_id: int) -> str:
    """Get log level ONLY from database"""
    config = await get_tenant_config(tenant_id)
    log_level = config.get("logging", {}).get("log_level", "INFO")
    return log_level.upper()


async def get_session_config(tenant_id: int) -> Dict[str, Any]:
    """Get session config ONLY from database"""
    config = await get_tenant_config(tenant_id)
    session_config = config.get("session", {})
    if not session_config:
        raise ValueError(f"Session configuration not found for tenant {tenant_id}")
    return session_config


async def get_rate_limit_config(tenant_id: int) -> Dict[str, Any]:
    """Get rate limit config ONLY from database"""
    config = await get_tenant_config(tenant_id)
    rate_limit_config = config.get("rate_limit", {})
    if not rate_limit_config:
        raise ValueError(f"Rate limit configuration not found for tenant {tenant_id}")
    return rate_limit_config


def clear_tenant_config_cache(tenant_id: Optional[int] = None):
    """Clear configuration cache"""
    if tenant_id:
        get_tenant_config.cache_clear()
        logger.info(f"Config cache cleared for tenant {tenant_id}")
    else:
        get_tenant_config.cache_clear()
        logger.info("All tenant config caches cleared")


# Alias for backward compatibility
get_tenant_settings = get_tenant_config