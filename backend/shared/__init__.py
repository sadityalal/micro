# Shared modules package initialization

from .auth_middleware import auth_middleware
from .password_policy_middleware import password_policy
from .rate_limit_middleware import GlobalRateLimiterMiddleware
from .role_middleware import (
    require_permission,
    require_role,
    require_any_permission,
    clear_permission_cache,
    ADMIN_PERMISSIONS,
    CUSTOMER_PERMISSIONS,
    MANAGER_PERMISSIONS
)
from .session_middleware import SecureSessionMiddleware, create_and_set_session
from .infrastructure_service import infra_service
from .logger import get_logger, setup_logging, RequestContext
from .database import get_db, init_db, close_db, async_session, Base
from .config import settings, get_tenant_settings
from .models import (
    RateLimitSettings,
    SessionSettings,
    InfrastructureSettings,
    SecuritySettings,
    RateLimitStrategy,
    SessionStorageType,
    SessionTimeoutType,
    ServiceStatus
)

__all__ = [
    # Middleware
    "auth_middleware",
    "password_policy",
    "GlobalRateLimiterMiddleware",
    "SecureSessionMiddleware",
    "create_and_set_session",
    "session_service",
    "SessionService",

    # Role and Permissions
    "require_permission",
    "require_role",
    "require_any_permission",
    "clear_permission_cache",
    "ADMIN_PERMISSIONS",
    "CUSTOMER_PERMISSIONS",
    "MANAGER_PERMISSIONS",

    # Infrastructure
    "infra_service",

    # Database
    "get_db",
    "init_db",
    "close_db",
    "async_session",
    "Base",

    # Logging
    "get_logger",
    "setup_logging",
    "RequestContext",

    # Config
    "settings",
    "get_tenant_settings",

    # Models
    "RateLimitSettings",
    "SessionSettings",
    "InfrastructureSettings",
    "SecuritySettings",
    "RateLimitStrategy",
    "SessionStorageType",
    "SessionTimeoutType",
    "ServiceStatus"
]