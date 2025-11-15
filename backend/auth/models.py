from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
import re

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

    @validator('first_name', 'last_name')
    def name_length(cls, v):
        if len(v) < 2:
            raise ValueError('Name must be at least 2 characters long')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    roles: List[str]
    created_at: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse

class LogoutResponse(BaseModel):
    message: str
    timestamp: float

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: float

class TokenRefresh(BaseModel):
    refresh_token: str

class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class PasswordValidationResponse(BaseModel):
    valid: bool
    score: int
    strength: str
    errors: List[str]

class SessionInfo(BaseModel):
    session_id: str
    user_id: int
    created_at: float
    expires_at: float
    ip_address: str
    user_agent: str