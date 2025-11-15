# backend/shared/models.py
"""
SQLAlchemy models — 1:1 mapping with 01-init.sql
100% matches your PostgreSQL schema
Zero drift. Zero surprise.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum, Text,
    ForeignKey, JSONB, Index, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from .database import Base


# =============================================================================
# Enums — must match PostgreSQL enums exactly
# =============================================================================
class RateLimitStrategy(enum.Enum):
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


class SessionStorageType(enum.Enum):
    REDIS = "redis"
    DATABASE = "database"
    JWT = "jwt"


class SessionTimeoutType(enum.Enum):
    ABSOLUTE = "absolute"
    SLIDING = "sliding"


class ServiceStatus(enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"


# =============================================================================
# Core Tenant Settings Models
# =============================================================================
class RateLimitSettings(Base):
    __tablename__ = "rate_limit_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_rate_limit_tenant"),
        Index("ix_rate_limit_tenant", "tenant_id"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True, unique=True)
    strategy = Column(Enum(RateLimitStrategy), default=RateLimitStrategy.FIXED_WINDOW)
    requests_per_minute = Column(Integer, default=60)
    requests_per_hour = Column(Integer, default=1000)
    requests_per_day = Column(Integer, default=10000)
    burst_capacity = Column(Integer, default=10)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class SessionSettings(Base):
    __tablename__ = "session_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_session_tenant"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True, unique=True)
    storage_type = Column(Enum(SessionStorageType), default=SessionStorageType.REDIS)
    timeout_type = Column(Enum(SessionTimeoutType), default=SessionTimeoutType.SLIDING)
    session_timeout_minutes = Column(Integer, default=30)
    absolute_timeout_minutes = Column(Integer, default=480)
    sliding_timeout_minutes = Column(Integer, default=30)
    max_concurrent_sessions = Column(Integer, default=5)
    regenerate_session = Column(Boolean, default=True)
    secure_cookies = Column(Boolean, default=True)
    http_only_cookies = Column(Boolean, default=True)
    same_site_policy = Column(String(20), default="lax")
    cookie_domain = Column(String(255))
    cookie_path = Column(String(100), default="/")
    enable_session_cleanup = Column(Boolean, default=True)
    cleanup_interval_minutes = Column(Integer, default=60)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class InfrastructureSettings(Base):
    __tablename__ = "infrastructure_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "service_name", name="uq_infra_tenant_service"),
        Index("ix_infra_tenant", "tenant_id"),
        Index("ix_infra_type", "service_type"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    service_name = Column(String(100), nullable=False)  # e.g., cache_redis, session_redis, message_queue
    service_type = Column(String(50), nullable=False)   # redis, rabbitmq, kafka, postgresql
    host = Column(String(255), nullable=False)
    port = Column(Integer)
    username = Column(String(255))
    password = Column(String(255))
    database_name = Column(String(100))
    connection_string = Column(Text)
    max_connections = Column(Integer, default=20)
    timeout_seconds = Column(Integer, default=30)
    status = Column(Enum(ServiceStatus), default=ServiceStatus.ACTIVE)
    health_check_url = Column(String(500))
    metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class SecuritySettings(Base):
    __tablename__ = "security_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_security_tenant"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True, unique=True)
    jwt_secret_key = Column(String(255), nullable=False)
    jwt_algorithm = Column(String(20), default="HS256")
    access_token_expiry_minutes = Column(Integer, default=30)
    refresh_token_expiry_days = Column(Integer, default=7)
    password_reset_expiry_minutes = Column(Integer, default=30)
    max_login_attempts = Column(Integer, default=5)
    account_lockout_minutes = Column(Integer, default=30)
    require_https = Column(Boolean, default=True)
    cors_origins = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())