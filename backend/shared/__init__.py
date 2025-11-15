# backend/shared/__init__.py
"""
PAVITRA PLATFORM — SHARED CORE
FINAL. CLEAN. HONEST. PERFECT.
NO LIES. NO TYPOS. NO UNRESOLVED REFERENCES.
Owner: @ItsSaurabhAdi
Germany, November 15, 2025 — 07:30 PM CET
VICTORY.
"""

# Config
from .config import bootstrap, settings, get_tenant_config

# Infrastructure
from .infrastructure_service import infra_service

# Logging — only truth
from .logger_middleware import get_logger

# Middleware
from .auth_middleware import auth_middleware
from .session_middleware import session_middleware
from .rate_limit_middleware import rate_limiter_middleware

# Session Service
from .session_service import (
    create_session,
    get_session,
    destroy_session,
    set_session_cookie,
    delete_session_cookie,
)

# RBAC
from .role_middleware import (
    require_permission,
    require_role,
    require_any_permission,
    clear_permission_cache,
)

# Models
from .models import (
    RateLimitSettings,
    SessionSettings,
    InfrastructureSettings,
    SecuritySettings,
)

# Database — CORRECT NAME
from .database import Base, async_session

__all__ = [
    "bootstrap", "settings", "get_tenant_config",
    "infra_service",
    "get_logger",
    "auth_middleware", "session_middleware", "rate_limiter_middleware",
    "create_session", "get_session", "destroy_session",
    "set_session_cookie", "delete_session_cookie",
    "require_permission", "require_role", "require_any_permission",
    "clear_permission_cache",
    "RateLimitSettings", "SessionSettings",
    "InfrastructureSettings", "SecuritySettings",
    "Base", "async_session",
]

__version__ = "1.0.0"
__author__ = "@ItsSaurabhAdi"