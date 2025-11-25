import httpx
from typing import Dict, Any
from shared.logger import auth_service_logger

class NotificationHelper:
    @staticmethod
    async def send_notification(event_type: str, tenant_id: int, recipient_id: int = None, data: Dict[str, Any] = None, priority: str = "medium"):
        """
        Send notification via notification service
        """
        try:
            # Real implementation - call notification service via HTTP
            async with httpx.AsyncClient() as client:
                notification_data = {
                    "event_type": event_type,
                    "tenant_id": tenant_id,
                    "recipient_id": recipient_id,
                    "data": data or {},
                    "priority": priority
                }
                response = await client.post(
                    "http://notification-service:8005/api/v1/notifications/send",
                    json=notification_data,
                    timeout=10.0
                )
                if response.status_code == 200:
                    auth_service_logger.info(f"Notification sent successfully: {event_type}")
                    return True
                else:
                    auth_service_logger.error(f"Failed to send notification: {response.status_code} - {response.text}")
                    return False
            
        except Exception as e:
            auth_service_logger.error(f"Error sending notification: {e}")
            return False

    @staticmethod
    async def send_user_registered_notification(tenant_id: int, user_data: Dict[str, Any], is_admin: bool = False):
        """
        Send user registration notification
        """
        if is_admin:
            # Send to admin about new user registration
            success = await NotificationHelper.send_notification(
                event_type="user_registered",
                tenant_id=tenant_id,
                data={
                    "user_id": user_data.get("id"),
                    "user_first_name": user_data.get("first_name"),
                    "user_last_name": user_data.get("last_name"),
                    "user_email": user_data.get("email"),
                    "user_phone": user_data.get("phone"),
                    "username": user_data.get("username"),
                    "registration_date": user_data.get("created_at")
                },
                priority="medium"
            )
        else:
            # Send welcome notification to user
            success = await NotificationHelper.send_notification(
                event_type="user_registered",
                tenant_id=tenant_id,
                recipient_id=user_data.get("id"),
                data={
                    "user_first_name": user_data.get("first_name"),
                    "user_last_name": user_data.get("last_name"),
                    "user_email": user_data.get("email"),
                    "username": user_data.get("username"),
                    "registration_date": user_data.get("created_at")
                },
                priority="medium"
            )
        return success
