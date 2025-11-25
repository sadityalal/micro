from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from shared.database.connection import get_db
from shared.database.repositories.user_repository import UserRepository
from .schemas import (
    NotificationRequest, NotificationResponse, NotificationEventType,
    NotificationPriority
)
from .notification_service import NotificationService

router = APIRouter()
notification_service = NotificationService()

@router.post("/send", response_model=dict)
async def send_notification(
    notification_request: NotificationRequest,
    background_tasks: BackgroundTasks
):
    """
    Send a notification immediately
    """
    try:
        # Validate event type
        if not any(notification_request.event_type == event for event in NotificationEventType):
            raise HTTPException(status_code=400, detail="Invalid event type")

        # Publish to RabbitMQ for async processing
        background_tasks.add_task(
            notification_service.publish_notification,
            notification_request
        )

        return {
            "message": "Notification queued for processing",
            "event_type": notification_request.event_type.value,
            "tenant_id": notification_request.tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue notification: {str(e)}")

@router.post("/user-registered")
async def notify_user_registered(
    user_id: int,
    tenant_id: int,
    background_tasks: BackgroundTasks
):
    """
    Send notifications when a new user registers
    """
    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        
        user = user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Notification for admins
        admin_notification = NotificationRequest(
            event_type=NotificationEventType.USER_REGISTERED,
            tenant_id=tenant_id,
            data={
                "user_id": user.id,
                "user_first_name": user.first_name,
                "user_last_name": user.last_name,
                "user_email": user.email,
                "user_phone": user.phone,
                "username": user.username,
                "registration_date": datetime.now().isoformat()
            },
            priority=NotificationPriority.MEDIUM
        )

        # Notification for the user
        user_notification = NotificationRequest(
            event_type=NotificationEventType.USER_REGISTERED,
            recipient_id=user_id,
            tenant_id=tenant_id,
            data={
                "user_first_name": user.first_name,
                "user_last_name": user.last_name,
                "user_email": user.email,
                "username": user.username,
                "registration_date": datetime.now().isoformat()
            },
            priority=NotificationPriority.MEDIUM
        )

        # Queue both notifications
        background_tasks.add_task(
            notification_service.publish_notification,
            admin_notification
        )
        background_tasks.add_task(
            notification_service.publish_notification,
            user_notification
        )

        return {
            "message": "User registration notifications queued",
            "user_id": user_id,
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue user registration notifications: {str(e)}")

@router.post("/password-reset")
async def notify_password_reset(
    user_id: int,
    tenant_id: int,
    otp_code: str,
    otp_expiry_minutes: int = 10,
    background_tasks: BackgroundTasks = None
):
    """
    Send password reset notification
    """
    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        
        user = user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        notification_request = NotificationRequest(
            event_type=NotificationEventType.PASSWORD_RESET,
            recipient_id=user_id,
            tenant_id=tenant_id,
            data={
                "user_first_name": user.first_name,
                "user_last_name": user.last_name,
                "user_email": user.email,
                "otp_code": otp_code,
                "otp_expiry_minutes": otp_expiry_minutes
            },
            priority=NotificationPriority.HIGH
        )

        if background_tasks:
            background_tasks.add_task(
                notification_service.publish_notification,
                notification_request
            )
        else:
            # Direct processing if no background tasks available
            await notification_service.process_notification(notification_request)

        return {
            "message": "Password reset notification sent",
            "user_id": user_id,
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send password reset notification: {str(e)}")

@router.post("/forgot-password-otp")
async def notify_forgot_password_otp(
    email: str,
    tenant_id: int,
    otp_code: str,
    otp_expiry_minutes: int = 10,
    background_tasks: BackgroundTasks = None
):
    """
    Send forgot password OTP notification
    """
    try:
        notification_request = NotificationRequest(
            event_type=NotificationEventType.FORGOT_PASSWORD_OTP,
            recipient_email=email,
            tenant_id=tenant_id,
            data={
                "otp_code": otp_code,
                "otp_expiry_minutes": otp_expiry_minutes
            },
            priority=NotificationPriority.HIGH
        )

        if background_tasks:
            background_tasks.add_task(
                notification_service.publish_notification,
                notification_request
            )
        else:
            await notification_service.process_notification(notification_request)

        return {
            "message": "Forgot password OTP sent",
            "email": email,
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send forgot password OTP: {str(e)}")

@router.post("/login-otp")
async def notify_login_otp(
    user_id: int,
    tenant_id: int,
    otp_code: str,
    otp_expiry_minutes: int = 10,
    background_tasks: BackgroundTasks = None
):
    """
    Send login OTP notification
    """
    try:
        db = next(get_db())
        user_repo = UserRepository(db)
        
        user = user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        notification_request = NotificationRequest(
            event_type=NotificationEventType.LOGIN_OTP,
            recipient_id=user_id,
            tenant_id=tenant_id,
            data={
                "user_first_name": user.first_name,
                "otp_code": otp_code,
                "otp_expiry_minutes": otp_expiry_minutes
            },
            priority=NotificationPriority.HIGH
        )

        if background_tasks:
            background_tasks.add_task(
                notification_service.publish_notification,
                notification_request
            )
        else:
            await notification_service.process_notification(notification_request)

        return {
            "message": "Login OTP sent",
            "user_id": user_id,
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send login OTP: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "notification-service",
        "timestamp": datetime.now().isoformat()
    }
