from typing import Dict, Any, Optional, List
import json


class DatabaseConfigService:
    def __init__(self):
        self._cache = {}
        self._system_cache = {}

    def get_system_config(self, db_session) -> Dict[str, Any]:
        """Get system-wide configuration from database"""
        if "system" in self._system_cache:
            return self._system_cache["system"]

        from shared.database.models import SystemSettings

        system_settings = db_session.query(SystemSettings).all()
        config = {}

        for setting in system_settings:
            if setting.setting_type == 'integer':
                config[setting.setting_key] = int(setting.setting_value) if setting.setting_value else None
            elif setting.setting_type == 'boolean':
                config[
                    setting.setting_key] = setting.setting_value.lower() == 'true' if setting.setting_value else False
            elif setting.setting_type == 'json':
                config[setting.setting_key] = json.loads(setting.setting_value) if setting.setting_value else {}
            else:
                config[setting.setting_key] = setting.setting_value

        self._system_cache["system"] = config
        return config

    def get_tenant_config(self, db_session, tenant_id: int) -> Dict[str, Any]:
        """Get complete configuration for a tenant"""
        if tenant_id in self._cache:
            return self._cache[tenant_id]

        from shared.database.repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(db_session)

        # Fetch all tenant-specific settings
        security_settings = tenant_repo.get_tenant_security_settings(tenant_id)
        login_settings = tenant_repo.get_tenant_login_settings(tenant_id)
        session_settings = tenant_repo.get_tenant_session_settings(tenant_id)
        rate_limit_settings = tenant_repo.get_tenant_rate_limit_settings(tenant_id)
        logging_settings = tenant_repo.get_tenant_logging_settings(tenant_id)
        site_settings = tenant_repo.get_site_settings(tenant_id)

        config = {
            "security": {
                "jwt_secret_key": security_settings.jwt_secret_key,
                "jwt_algorithm": security_settings.jwt_algorithm,
                "access_token_expiry_minutes": security_settings.access_token_expiry_minutes,
                "refresh_token_expiry_days": security_settings.refresh_token_expiry_days,
                "password_reset_expiry_minutes": security_settings.password_reset_expiry_minutes,
                "max_login_attempts": security_settings.max_login_attempts,
                "account_lockout_minutes": security_settings.account_lockout_minutes,
                "require_https": security_settings.require_https,
                "cors_origins": security_settings.cors_origins or ["http://localhost:3000"]
            },
            "login": {
                "password_policy": login_settings.password_policy.value,
                "min_password_length": login_settings.min_password_length,
                "require_uppercase": login_settings.require_uppercase,
                "require_lowercase": login_settings.require_lowercase,
                "require_numbers": login_settings.require_numbers,
                "require_special_chars": login_settings.require_special_chars,
                "max_password_age_days": login_settings.max_password_age_days,
                "password_history_count": login_settings.password_history_count,
                "max_login_attempts": login_settings.max_login_attempts,
                "lockout_duration_minutes": login_settings.lockout_duration_minutes,
                "username_policy": login_settings.username_policy.value,
                "session_timeout_minutes": login_settings.session_timeout_minutes,
                "mfa_required": login_settings.mfa_required
            },
            "session": {
                "storage_type": session_settings.storage_type.value,
                "timeout_type": session_settings.timeout_type.value,
                "session_timeout_minutes": session_settings.session_timeout_minutes,
                "absolute_timeout_minutes": session_settings.absolute_timeout_minutes,
                "sliding_timeout_minutes": session_settings.sliding_timeout_minutes,
                "max_concurrent_sessions": session_settings.max_concurrent_sessions,
                "regenerate_session": session_settings.regenerate_session,
                "secure_cookies": session_settings.secure_cookies,
                "http_only_cookies": session_settings.http_only_cookies,
                "same_site_policy": session_settings.same_site_policy,
                "cookie_domain": session_settings.cookie_domain,
                "cookie_path": session_settings.cookie_path,
                "enable_session_cleanup": session_settings.enable_session_cleanup,
                "cleanup_interval_minutes": session_settings.cleanup_interval_minutes
            },
            "rate_limit": {
                "strategy": rate_limit_settings.strategy.value,
                "requests_per_minute": rate_limit_settings.requests_per_minute,
                "requests_per_hour": rate_limit_settings.requests_per_hour,
                "requests_per_day": rate_limit_settings.requests_per_day,
                "burst_capacity": rate_limit_settings.burst_capacity,
                "enabled": rate_limit_settings.enabled
            },
            "logging": {
                "log_level": logging_settings.log_level,
                "enable_audit_log": logging_settings.enable_audit_log,
                "enable_access_log": logging_settings.enable_access_log,
                "enable_security_log": logging_settings.enable_security_log,
                "retention_days": logging_settings.retention_days
            },
            "site": site_settings
        }

        self._cache[tenant_id] = config
        return config

    def get_service_url(self, db_session, tenant_id: int, service_name: str) -> str:
        """Get specific service URL for a tenant"""
        from shared.database.repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(db_session)
        service_urls = tenant_repo.get_service_urls(tenant_id)

        for service in service_urls:
            if service.service_name == service_name:
                return service.base_url
        return ""

    def get_database_url(self, db_session, tenant_id: int) -> str:
        """Get database URL for a tenant"""
        from shared.database.repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(db_session)
        infra_settings = tenant_repo.get_infrastructure_settings(tenant_id)

        for setting in infra_settings:
            if setting.service_type == 'postgresql':
                return f"postgresql://{setting.username}:{setting.password}@{setting.host}:{setting.port}/{setting.database_name}"
        return ""

    def get_redis_url(self, db_session, tenant_id: int) -> str:
        """Get Redis URL for a tenant"""
        from shared.database.repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(db_session)
        infra_settings = tenant_repo.get_infrastructure_settings(tenant_id)

        for setting in infra_settings:
            if setting.service_type == 'redis':
                return f"redis://{setting.host}:{setting.port}/{setting.database_name}"
        return ""

    def get_service_config(self, db_session, tenant_id: int, service_name: str) -> Dict[str, Any]:
        """Get complete service configuration for a tenant"""
        from shared.database.repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(db_session)
        service_urls = tenant_repo.get_service_urls(tenant_id)

        for service in service_urls:
            if service.service_name == service_name:
                return {
                    "base_url": service.base_url,
                    "health_endpoint": service.health_endpoint,
                    "timeout_ms": service.timeout_ms,
                    "retry_attempts": service.retry_attempts,
                    "circuit_breaker_enabled": service.circuit_breaker_enabled
                }
        return {}

    def clear_cache(self, tenant_id: Optional[int] = None):
        """Clear configuration cache"""
        if tenant_id:
            self._cache.pop(tenant_id, None)
        else:
            self._cache.clear()
            self._system_cache.clear()


# Global instance
db_config_service = DatabaseConfigService()