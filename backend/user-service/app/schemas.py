from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class DeletionType(str, Enum):
    ANONYMIZE = "anonymize"
    FULL_DELETE = "full_delete"

class ConsentType(str, Enum):
    PRIVACY_POLICY = "privacy_policy"
    MARKETING = "marketing"
    COOKIES = "cookies"
    TERMS_OF_SERVICE = "terms_of_service"

class UserProfileResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    username: Optional[str]
    phone: Optional[str]
    tenant_id: Optional[int]
    created_at: datetime
    updated_at: datetime

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    username: Optional[str] = None

    @validator('phone')
    def validate_phone(cls, v):
        if v and not v.replace('+', '').replace(' ', '').isdigit():
            raise ValueError('Phone number must contain only digits and optional + prefix')
        return v

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class AddressCreate(BaseModel):
    type: str  # home, work, billing, shipping
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    country: str
    postal_code: str
    is_default: bool = False

    @validator('type')
    def validate_address_type(cls, v):
        allowed_types = ['home', 'work', 'billing', 'shipping']
        if v not in allowed_types:
            raise ValueError(f'Address type must be one of: {", ".join(allowed_types)}')
        return v

class AddressResponse(BaseModel):
    id: int
    type: str
    address_line1: str
    address_line2: Optional[str]
    city: str
    state: str
    country: str
    postal_code: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

class AddressUpdate(BaseModel):
    type: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    is_default: Optional[bool] = None

class UserPreferences(BaseModel):
    language: Optional[str] = "en"
    currency: Optional[str] = "USD"
    timezone: Optional[str] = "UTC"
    email_notifications: Optional[bool] = True
    sms_notifications: Optional[bool] = False
    marketing_emails: Optional[bool] = False
    two_factor_enabled: Optional[bool] = False

class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    last_accessed: str
    expires_at: str
    user_agent: Optional[str]
    ip_address: Optional[str]

class LoginHistoryResponse(BaseModel):
    login_time: datetime
    logout_time: Optional[datetime]
    ip_address: Optional[str]
    device_info: Optional[Dict[str, Any]]
    status: str

class AccountDeactivationRequest(BaseModel):
    reason: Optional[str] = None
    feedback: Optional[str] = None

class ConsentRequest(BaseModel):
    consent_type: ConsentType
    granted: bool
    version: str

class DataDeletionRequest(BaseModel):
    deletion_type: DeletionType
    reason: Optional[str] = None

    @validator('deletion_type')
    def validate_deletion_type(cls, v):
        if v not in [DeletionType.ANONYMIZE, DeletionType.FULL_DELETE]:
            raise ValueError('Deletion type must be "anonymize" or "full_delete"')
        return v
