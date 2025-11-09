from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime


# Auth Schemas
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


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: int
    tenant_id: int
    email: str


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    avatar_url: Optional[str]
    email_verified: bool
    role_id: int

    class Config:
        from_attributes = True


# Cart Schemas
class CartItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    unit_price: float


class CartResponse(BaseModel):
    id: int
    user_id: Optional[int]
    session_id: Optional[str]
    items: List[CartItem]
    total_amount: float
    item_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CartMergeRequest(BaseModel):
    session_id: str