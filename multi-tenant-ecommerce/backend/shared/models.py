from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, DECIMAL, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    domain = Column(String(255), unique=True)
    subdomain = Column(String(100), unique=True)
    status = Column(String(20), default='active')
    plan_type = Column(String(50), default='starter')
    features = Column(JSON, default=dict)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    level = Column(Integer, unique=True, nullable=False)
    permissions = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('user_roles.id'), default=5)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    avatar_url = Column(String(500))
    status = Column(String(20), default='active')
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    locked_until = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(100))
    last_login = Column(DateTime)
    last_password_change = Column(DateTime)
    last_activity = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    # Relationships
    tenant = relationship("Tenant")
    role = relationship("UserRole")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_token = Column(String(500), unique=True, nullable=False)
    refresh_token = Column(String(500))
    device_id = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    location = Column(JSON)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    refresh_token_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    last_used_at = Column(DateTime, default=func.now())

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User")