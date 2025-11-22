from sqlalchemy.orm import Session
from ..models import (
    Tenant, SecuritySettings, LoginSettings, SessionSettings,
    RateLimitSettings, LoggingSettings, SystemSettings, SiteSettings,
    TenantSystemSettings, InfrastructureSettings, ServiceUrls
)
from typing import Optional, Dict, List

class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.domain == domain).first()

    def get_tenant_security_settings(self, tenant_id: int) -> Optional[SecuritySettings]:
        return self.db.query(SecuritySettings).filter(SecuritySettings.tenant_id == tenant_id).first()

    def get_tenant_login_settings(self, tenant_id: int) -> Optional[LoginSettings]:
        return self.db.query(LoginSettings).filter(LoginSettings.tenant_id == tenant_id).first()

    def get_tenant_session_settings(self, tenant_id: int) -> Optional[SessionSettings]:
        return self.db.query(SessionSettings).filter(SessionSettings.tenant_id == tenant_id).first()

    def get_tenant_rate_limit_settings(self, tenant_id: int) -> Optional[RateLimitSettings]:
        return self.db.query(RateLimitSettings).filter(RateLimitSettings.tenant_id == tenant_id).first()

    def get_tenant_logging_settings(self, tenant_id: int) -> Optional[LoggingSettings]:
        return self.db.query(LoggingSettings).filter(LoggingSettings.tenant_id == tenant_id).first()

    def get_system_setting(self, key: str) -> Optional[str]:
        setting = self.db.query(SystemSettings).filter(SystemSettings.setting_key == key).first()
        return setting.setting_value if setting else None

    def get_tenant_system_settings(self, tenant_id: int) -> Dict[str, str]:
        settings = self.db.query(TenantSystemSettings).filter(TenantSystemSettings.tenant_id == tenant_id).all()
        return {setting.setting_key: setting.setting_value for setting in settings}

    def get_site_settings(self, tenant_id: int) -> Dict[str, str]:
        settings = self.db.query(SiteSettings).filter(SiteSettings.tenant_id == tenant_id).all()
        return {setting.setting_key: setting.setting_value for setting in settings}

    def get_infrastructure_settings(self, tenant_id: int) -> List[Dict]:
        settings = self.db.query(InfrastructureSettings).filter(InfrastructureSettings.tenant_id == tenant_id).all()
        return [
            {
                "service_name": setting.service_name,
                "service_type": setting.service_type,
                "host": setting.host,
                "port": setting.port,
                "status": setting.status.value
            }
            for setting in settings
        ]

    def get_service_urls(self, tenant_id: int) -> List[Dict]:
        services = self.db.query(ServiceUrls).filter(ServiceUrls.tenant_id == tenant_id).all()
        return [
            {
                "service_name": service.service_name,
                "base_url": service.base_url,
                "health_endpoint": service.health_endpoint,
                "status": service.status.value
            }
            for service in services
        ]

    def get_all_active_tenants(self) -> List[Tenant]:
        return self.db.query(Tenant).filter(Tenant.status == 'active').all()