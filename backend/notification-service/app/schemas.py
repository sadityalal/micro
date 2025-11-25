from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from enum import Enum

class NotificationEventType(str, Enum):
    USER_REGISTERED = "user_registered"
    PASSWORD_RESET = "password_reset"
    FORGOT_PASSWORD_OTP = "forgot_password_otp"
    LOGIN_OTP = "login_otp"

class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    PUSH = "push"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class NotificationRequest(BaseModel):
    event_type: NotificationEventType
    recipient_id: Optional[int] = None
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = None
    tenant_id: int
    data: Dict[str, Any]
    priority: NotificationPriority = NotificationPriority.MEDIUM

class NotificationResponse(BaseModel):
    message: str
    event_type: str
    tenant_id: int

class NotificationMessage(BaseModel):
    subject: str
    body: str
    type: NotificationType
