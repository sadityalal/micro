from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Float, Text
from sqlalchemy.sql import func
from .database import Base
import enum


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


class RateLimitSettings(Base):
    __tablename__ = "rate_limit_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    strategy = Column(Enum(RateLimitStrategy), default=RateLimitStrategy.FIXED_WINDOW)
    requests_per_minute = Column(Integer, default=60)
    requests_per_hour = Column(Integer, default=1000)
    requests_per_day = Column(Integer, default=10000)
    burst_capacity = Column(Integer, default=10)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SessionSettings(Base):
    __tablename__ = "session_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    storage_type = Column(Enum(SessionStorageType), default=SessionStorageType.REDIS)
    timeout_type = Column(Enum(SessionTimeoutType), default=SessionTimeoutType.SLIDING)
    session_timeout_minutes = Column(Integer, default=30)
    absolute_timeout_minutes = Column(Integer, default=480)
    sliding_timeout_minutes = Column(Integer, default=30)
    max_concurrent_sessions = Column(Integer, default=5)
    regenerate_session = Column(Boolean, default=True)
    secure_cookies = Column(Boolean, default=True)
    http_only_cookies = Column(Boolean, default=True)
    same_site_policy = Column(String(20), default='lax')
    cookie_domain = Column(String(255))
    cookie_path = Column(String(100), default='/')
    enable_session_cleanup = Column(Boolean, default=True)
    cleanup_interval_minutes = Column(Integer, default=60)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class InfrastructureSettings(Base):
    __tablename__ = "infrastructure_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    service_name = Column(String(100), nullable=False)
    service_type = Column(String(50), nullable=False)
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
    metadata = Column(Text)  # JSON as string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SecuritySettings(Base):
    __tablename__ = "security_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    jwt_secret_key = Column(String(255), nullable=False)
    jwt_algorithm = Column(String(20), default='HS256')
    access_token_expiry_minutes = Column(Integer, default=30)
    refresh_token_expiry_days = Column(Integer, default=7)
    password_reset_expiry_minutes = Column(Integer, default=30)
    max_login_attempts = Column(Integer, default=5)
    account_lockout_minutes = Column(Integer, default=30)
    require_https = Column(Boolean, default=True)
    cors_origins = Column(Text)  # JSON as string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())