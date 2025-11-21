import os
from typing import Dict, Any, Optional
from functools import lru_cache
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from sqlalchemy import text
from .database import async_session
from .logger_middleware import get_logger

logger = get_logger(__name__)


class DatabaseSettings(BaseSettings):
    url: str = Field(..., env="DATABASE_URL")
    echo: bool = Field(False, env="DATABASE_ECHO")
    pool_size: int = Field(5, env="DATABASE_POOL_SIZE")
    max_overflow: int = Field(10, env="DATABASE_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    pool_recycle: int = Field(3600, env="DATABASE_POOL_RECYCLE")
    ssl_enabled: bool = Field(False, env="DATABASE_SSL_ENABLED")


class AppSettings(BaseSettings):
    name: str = Field("Pavitra Platform", env="APP_NAME")
    environment: str = Field("production", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")


class BootstrapSettings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    app_name: str = Field("Pavitra Platform", env="APP_NAME")
    environment: str = Field("production", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    app: AppSettings = Field(default_factory=AppSettings)

    @validator('database', pre=True, always=True)
    def set_database_defaults(cls, v, values):
        if isinstance(v, dict):
            return DatabaseSettings(
                url=values.get('database_url', ''),
                echo=values.get('debug', False),
                pool_size=values.get('database_pool_size', 5),
                max_overflow=values.get('database_max_overflow', 10),
                pool_timeout=values.get('database_pool_timeout', 30),
                pool_recycle=values.get('database_pool_recycle', 3600),
                ssl_enabled=values.get('database_ssl_enabled', False),
                **v
            )
        return v or DatabaseSettings(
            url=values.get('database_url', ''),
            echo=values.get('debug', False),
            pool_size=values.get('database_pool_size', 5),
            max_overflow=values.get('database_max_overflow', 10),
            pool_timeout=values.get('database_pool_timeout', 30),
            pool_recycle=values.get('database_pool_recycle', 3600),
            ssl_enabled=values.get('database_ssl_enabled', False)
        )

    @validator('app', pre=True, always=True)
    def set_app_defaults(cls, v, values):
        if isinstance(v, dict):
            return AppSettings(
                name=values.get('app_name', 'Pavitra Platform'),
                environment=values.get('environment', 'production'),
                debug=values.get('debug', False),
                log_level=values.get('log_level', 'INFO'),
                **v
            )
        return v or AppSettings(
            name=values.get('app_name', 'Pavitra Platform'),
            environment=values.get('environment', 'production'),
            debug=values.get('debug', False),
            log_level=values.get('log_level', 'INFO')
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


bootstrap = BootstrapSettings()
settings = bootstrap


@lru_cache(maxsize=128)
async def get_tenant_config(tenant_id: int) -> Dict[str, Any]:
    if tenant_id <= 0:
        logger.warning(f"Invalid tenant_id: {tenant_id}")
        return {}
    async with async_session() as db:
        try:
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

            # Add logging settings query
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
            sys_result = await db.execute(
                text("SELECT setting_key, setting_value FROM tenant_system_settings WHERE tenant_id = :tid"),
                {"tid": tenant_id}
            )
            system_settings = {row.setting_key: row.setting_value for row in sys_result.fetchall()}
            config = {
                "security": security._asdict() if security else {},
                "session": session._asdict() if session else {},
                "rate_limit": rate_limit._asdict() if rate_limit else {},
                "logging": logging_config._asdict() if logging_config else {},
                "infrastructure": infrastructure,
                "service_urls": service_urls,
                "system": system_settings,
            }
            logger.debug(f"Tenant {tenant_id} config loaded and cached")
            return config
        except Exception as e:
            logger.error(f"Failed to load config for tenant {tenant_id}: {e}", exc_info=True)
            return {}


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


async def get_system_setting(key: str, default: Any = None) -> Any:
    return default


def clear_tenant_config_cache(tenant_id: Optional[int] = None):
    """Clear configuration cache"""
    if tenant_id:
        get_tenant_config.cache_clear()
        logger.info(f"Config cache cleared for tenant {tenant_id}")
    else:
        get_tenant_config.cache_clear()
        logger.info("All tenant config caches cleared")


get_tenant_settings = get_tenant_config