from typing import Dict, Any
import os
import logging
from .database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DatabaseSettings:
    def __init__(self):
        self._cached_settings = {}

    def get_settings_from_db(self, tenant_id: int = 1) -> Dict[str, Any]:
        """Fetch ALL settings from database for a tenant - NO FALLBACKS"""
        db = next(get_db())

        try:
            # Fetch from session_settings table
            session_settings = db.execute(
                text("SELECT * FROM session_settings WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id}
            ).fetchone()

            # Fetch from rate_limit_settings table
            rate_settings = db.execute(
                text("SELECT * FROM rate_limit_settings WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id}
            ).fetchone()

            # Fetch from security_settings table
            security_settings = db.execute(
                text("SELECT * FROM security_settings WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id}
            ).fetchone()

            # Fetch from site_settings table
            site_settings = db.execute(
                text("SELECT setting_key, setting_value FROM site_settings WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id}
            ).fetchall()

            # Convert site_settings to dict
            site_settings_dict = {row.setting_key: row.setting_value for row in site_settings}

            # Build settings from database ONLY
            settings_dict = {
                # Database URLs
                "database_url": f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres:5432/{os.getenv('POSTGRES_DB')}",
                "redis_url": f"redis://:{os.getenv('REDIS_PASSWORD')}@redis:6379",
                "rabbitmq_url": f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASSWORD')}@rabbitmq:5672",

                # JWT from security_settings
                "jwt_secret": security_settings.jwt_secret,
                "jwt_algorithm": "HS256",
                "access_token_expire_minutes": session_settings.session_timeout // 60,
                "refresh_token_expire_days": 7,

                # Security
                "password_hashing_algorithm": "argon2",

                # Service URLs from site_settings
                "auth_service_url": site_settings_dict['auth_service_url'],
                "user_service_url": site_settings_dict['user_service_url'],
                "cart_service_url": site_settings_dict['cart_service_url'],
                "tenant_service_url": site_settings_dict['tenant_service_url'],
                "product_service_url": site_settings_dict['product_service_url'],
                "payment_service_url": site_settings_dict['payment_service_url'],
                "notification_service_url": site_settings_dict['notification_service_url'],

                # Rate Limiting from rate_limit_settings
                "rate_limit_requests_per_minute": rate_settings.requests_per_minute,
                "rate_limit_requests_per_hour": rate_settings.requests_per_hour,
                "burst_limit": rate_settings.burst_limit,

                # Session settings from session_settings
                "session_timeout": session_settings.session_timeout,
                "max_sessions_per_user": session_settings.max_sessions_per_user,
                "allow_concurrent_sessions": session_settings.allow_concurrent_sessions,
            }

            db.close()
            logger.info(f"Settings loaded from database for tenant {tenant_id}")
            return settings_dict

        except Exception as e:
            db.close()
            logger.error(f"Error fetching settings from database: {e}")
            raise RuntimeError(f"Failed to load settings from database: {e}")

    def get_settings(self, tenant_id: int = 1) -> Dict[str, Any]:
        """Get settings from database"""
        cache_key = f"settings_{tenant_id}"

        if cache_key not in self._cached_settings:
            self._cached_settings[cache_key] = self.get_settings_from_db(tenant_id)

        return self._cached_settings[cache_key]


# Global settings instance
db_settings = DatabaseSettings()


class Settings:
    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
        self._settings_data = db_settings.get_settings(tenant_id)

    @property
    def database_url(self) -> str:
        return self._settings_data["database_url"]

    @property
    def redis_url(self) -> str:
        return self._settings_data["redis_url"]

    @property
    def rabbitmq_url(self) -> str:
        return self._settings_data["rabbitmq_url"]

    @property
    def jwt_secret(self) -> str:
        return self._settings_data["jwt_secret"]

    @property
    def jwt_algorithm(self) -> str:
        return self._settings_data["jwt_algorithm"]

    @property
    def access_token_expire_minutes(self) -> int:
        return self._settings_data["access_token_expire_minutes"]

    @property
    def refresh_token_expire_days(self) -> int:
        return self._settings_data["refresh_token_expire_days"]

    @property
    def password_hashing_algorithm(self) -> str:
        return self._settings_data["password_hashing_algorithm"]

    @property
    def auth_service_url(self) -> str:
        return self._settings_data["auth_service_url"]

    @property
    def user_service_url(self) -> str:
        return self._settings_data["user_service_url"]

    @property
    def cart_service_url(self) -> str:
        return self._settings_data["cart_service_url"]

    @property
    def tenant_service_url(self) -> str:
        return self._settings_data["tenant_service_url"]

    @property
    def product_service_url(self) -> str:
        return self._settings_data["product_service_url"]

    @property
    def payment_service_url(self) -> str:
        return self._settings_data["payment_service_url"]

    @property
    def notification_service_url(self) -> str:
        return self._settings_data["notification_service_url"]

    @property
    def rate_limit_requests_per_minute(self) -> int:
        return self._settings_data["rate_limit_requests_per_minute"]

    @property
    def rate_limit_requests_per_hour(self) -> int:
        return self._settings_data["rate_limit_requests_per_hour"]

    @property
    def burst_limit(self) -> int:
        return self._settings_data["burst_limit"]

    @property
    def session_timeout(self) -> int:
        return self._settings_data["session_timeout"]

    @property
    def max_sessions_per_user(self) -> int:
        return self._settings_data["max_sessions_per_user"]

    @property
    def allow_concurrent_sessions(self) -> bool:
        return self._settings_data["allow_concurrent_sessions"]


def get_settings(tenant_id: int = 1) -> Settings:
    return Settings(tenant_id)