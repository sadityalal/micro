from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class TokenType(str, Enum):
    BEARER = "bearer"

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = TokenType.BEARER
    expires_in: int
    user_id: int
    tenant_id: Optional[int] = None
    roles: List[str] = []
    permissions: List[str] = []

class TokenData(BaseModel):
    user_id: int
    tenant_id: Optional[int] = None
    email: str
    roles: List[str] = []
    permissions: List[str] = []
    exp: datetime

class UserLogin(BaseModel):
    login_identifier: str
    password: str
    tenant_domain: Optional[str] = None

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    username: Optional[str] = None
    tenant_domain: Optional[str] = None

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    tenant_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PasswordResetRequest(BaseModel):
    email: EmailStr
    tenant_domain: Optional[str] = None

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class TenantInfo(BaseModel):
    id: int
    name: str
    domain: str
    status: str

class AuthConfig(BaseModel):
    security_settings: Dict[str, Any]
    login_settings: Dict[str, Any]
    session_settings: Dict[str, Any]
    rate_limit_settings: Dict[str, Any]