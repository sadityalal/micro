import aio_pika
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from shared.database.repositories.user_repository import UserRepository
from shared.database.repositories.tenant_repository import TenantRepository
from shared.database.connection import get_db, get_redis
from .schemas import (
    NotificationType, NotificationEventType, NotificationRequest,
    NotificationMessage, NotificationPriority
)
from .providers import (
    EmailProvider, SMSProvider, WhatsAppProvider, TelegramProvider
)
from .templating import TemplateManager
from shared.logger import setup_logger

class NotificationService:
    def __init__(self):
        self.logger = setup_logger("notification-service")
        self.template_manager = TemplateManager()
        self.email_provider = EmailProvider()
        self.sms_provider = SMSProvider()
        self.whatsapp_provider = WhatsAppProvider()
        self.telegram_provider = TelegramProvider()
        self.rabbitmq_connection = None
        self.channel = None

    async def initialize_rabbitmq(self):
        """Initialize RabbitMQ connection"""
        try:
            self.rabbitmq_connection = await aio_pika.connect_robust(
                "amqp://guest:guest@rabbitmq:5672/"
            )
            self.channel = await self.rabbitmq_connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            
            # Declare exchanges and queues
            await self.channel.declare_exchange(
                "notifications", 
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            
            # Main notification queue
            queue = await self.channel.declare_queue(
                "notification_queue",
                durable=True
            )
            await queue.bind("notifications", routing_key="notification")
            
            # High priority queue
            priority_queue = await self.channel.declare_queue(
                "priority_notification_queue",
                durable=True,
                arguments={
                    "x-max-priority": 10
                }
            )
            await priority_queue.bind("notifications", routing_key="priority")
            
            self.logger.info("RabbitMQ initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize RabbitMQ: {e}")
            raise

    async def publish_notification(self, notification_request: NotificationRequest):
        """Publish notification to RabbitMQ queue"""
        try:
            if not self.channel:
                await self.initialize_rabbitmq()

            # Determine routing key based on priority
            routing_key = "notification"
            if notification_request.priority in [NotificationPriority.HIGH, NotificationPriority.URGENT]:
                routing_key = "priority"

            message_body = json.dumps(notification_request.dict()).encode()
            
            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=self._get_priority_value(notification_request.priority)
            )
            
            await self.channel.default_exchange.publish(
                message,
                routing_key=routing_key
            )
            
            self.logger.info(
                f"Notification published to queue: {notification_request.event_type}",
                extra={
                    "event_type": notification_request.event_type.value,
                    "tenant_id": notification_request.tenant_id,
                    "priority": notification_request.priority.value
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to publish notification: {e}")
            raise

    def _get_priority_value(self, priority: NotificationPriority) -> int:
        """Convert priority enum to numeric value for RabbitMQ"""
        priority_map = {
            NotificationPriority.LOW: 1,
            NotificationPriority.MEDIUM: 5,
            NotificationPriority.HIGH: 8,
            NotificationPriority.URGENT: 10
        }
        return priority_map.get(priority, 5)

    async def process_notification(self, notification_request: NotificationRequest):
        """Process a single notification request"""
        try:
            db = next(get_db())
            user_repo = UserRepository(db)
            tenant_repo = TenantRepository(db)
            
            # Get tenant information
            tenant = tenant_repo.get_tenant_system_settings(notification_request.tenant_id)
            if not tenant:
                self.logger.error(f"Tenant not found: {notification_request.tenant_id}")
                return

            # Get user information if recipient_id is provided
            user_data = {}
            if notification_request.recipient_id:
                user = user_repo.get_user_by_id(notification_request.recipient_id)
                if user:
                    user_data = {
                        "user_id": user.id,
                        "user_first_name": user.first_name,
                        "user_last_name": user.last_name,
                        "user_email": user.email,
                        "user_phone": user.phone,
                        "username": user.username
                    }

            # Merge user data with notification data
            template_data = {
                **notification_request.data,
                **user_data,
                "tenant_name": tenant.name if hasattr(tenant, 'name') else "Our Store",
                "current_year": datetime.now().year,
                "timestamp": datetime.now().isoformat()
            }

            # Determine recipients and their preferences
            recipients = await self._get_recipients(notification_request, user_repo)
            
            sent_count = 0
            for recipient in recipients:
                try:
                    success = await self._send_notification_to_recipient(
                        recipient, notification_request, template_data
                    )
                    if success:
                        sent_count += 1
                except Exception as e:
                    self.logger.error(
                        f"Failed to send notification to recipient: {e}",
                        extra={"recipient": recipient}
                    )

            self.logger.info(
                f"Notification processing completed",
                extra={
                    "event_type": notification_request.event_type.value,
                    "total_recipients": len(recipients),
                    "sent_count": sent_count,
                    "tenant_id": notification_request.tenant_id
                }
            )

        except Exception as e:
            self.logger.error(f"Failed to process notification: {e}")
            raise

    async def _get_recipients(self, notification_request: NotificationRequest, user_repo: UserRepository) -> List[Dict]:
        """Get recipients based on notification type and preferences"""
        recipients = []
        
        if notification_request.event_type == NotificationEventType.USER_REGISTERED:
            # For user registration, notify admins
            admins = user_repo.get_users_by_role(["admin", "super_admin"])
            for admin in admins:
                preferences = user_repo.get_user_preferences(admin.id)
                if preferences and preferences.email_notifications:
                    recipients.append({
                        "type": NotificationType.EMAIL,
                        "email": admin.email,
                        "user_id": admin.id,
                        "is_admin": True
                    })
        else:
            # For other events, notify the specific user
            if notification_request.recipient_id:
                user = user_repo.get_user_by_id(notification_request.recipient_id)
                if user:
                    preferences = user_repo.get_user_preferences(user.id)
                    if preferences:
                        # Add email if enabled
                        if preferences.email_notifications and user.email:
                            recipients.append({
                                "type": NotificationType.EMAIL,
                                "email": user.email,
                                "user_id": user.id,
                                "is_admin": False
                            })
                        # Add SMS if enabled and phone exists
                        if preferences.sms_notifications and user.phone:
                            recipients.append({
                                "type": NotificationType.SMS,
                                "phone": user.phone,
                                "user_id": user.id,
                                "is_admin": False
                            })
            
            # Also include direct recipient information from request
            if notification_request.recipient_email:
                recipients.append({
                    "type": NotificationType.EMAIL,
                    "email": notification_request.recipient_email,
                    "user_id": notification_request.recipient_id,
                    "is_admin": False
                })
            if notification_request.recipient_phone:
                recipients.append({
                    "type": NotificationType.SMS,
                    "phone": notification_request.recipient_phone,
                    "user_id": notification_request.recipient_id,
                    "is_admin": False
                })

        return recipients

    async def _send_notification_to_recipient(self, recipient: Dict, notification_request: NotificationRequest, template_data: Dict):
        """Send notification to a single recipient"""
        try:
            notification_type = recipient["type"]
            
            # Render template
            subject, message = self.template_manager.render_template(
                notification_request.event_type,
                notification_type,
                template_data,
                recipient.get("is_admin", False)
            )
            
            # Send via appropriate provider
            if notification_type == NotificationType.EMAIL:
                success = await self.email_provider.send_email(
                    recipient["email"],
                    subject,
                    message,
                    notification_request.tenant_id
                )
            elif notification_type == NotificationType.SMS:
                success = await self.sms_provider.send_sms(
                    recipient["phone"],
                    message,
                    notification_request.tenant_id
                )
            elif notification_type == NotificationType.WHATSAPP:
                success = await self.whatsapp_provider.send_whatsapp(
                    recipient["phone"],
                    message,
                    notification_request.tenant_id
                )
            elif notification_type == NotificationType.TELEGRAM:
                success = await self.telegram_provider.send_telegram(
                    recipient.get("telegram_id", recipient.get("user_id")),
                    message,
                    notification_request.tenant_id
                )
            else:
                self.logger.warning(f"Unsupported notification type: {notification_type}")
                return False

            if success:
                self.logger.info(
                    f"Notification sent successfully",
                    extra={
                        "type": notification_type.value,
                        "event_type": notification_request.event_type.value,
                        "recipient": recipient.get('email') or recipient.get('phone'),
                        "tenant_id": notification_request.tenant_id
                    }
                )
            else:
                self.logger.error(
                    f"Failed to send notification",
                    extra={
                        "type": notification_type.value,
                        "event_type": notification_request.event_type.value,
                        "recipient": recipient.get('email') or recipient.get('phone'),
                        "tenant_id": notification_request.tenant_id
                    }
                )

            return success

        except Exception as e:
            self.logger.error(
                f"Error sending notification to recipient: {e}",
                extra={"recipient": recipient, "event_type": notification_request.event_type.value}
            )
            return False

    async def consume_notifications(self):
        """Start consuming notifications from RabbitMQ"""
        try:
            if not self.channel:
                await self.initialize_rabbitmq()

            queue = await self.channel.declare_queue("notification_queue", durable=True)
            
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            notification_data = json.loads(message.body.decode())
                            notification_request = NotificationRequest(**notification_data)
                            
                            await self.process_notification(notification_request)
                            
                        except Exception as e:
                            self.logger.error(f"Error processing message from queue: {e}")
                            # Don't requeue malformed messages
                            await message.reject(requeue=False)

        except Exception as e:
            self.logger.error(f"Error in notification consumer: {e}")
            raise

    async def close(self):
        """Close connections"""
        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()
