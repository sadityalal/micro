import aiosmtplib
import logging
from typing import Optional
from sqlalchemy.orm import Session
from shared.database.repositories.tenant_repository import TenantRepository
from shared.database.connection import get_db
from shared.logger import setup_logger

class BaseProvider:
    def __init__(self):
        self.logger = setup_logger(f"provider-{self.__class__.__name__.lower()}")

    def _get_tenant_settings(self, tenant_id: int, setting_key: str) -> Optional[str]:
        """Get tenant-specific settings from database"""
        try:
            db = next(get_db())
            tenant_repo = TenantRepository(db)
            settings = tenant_repo.get_tenant_notification_settings(tenant_id)
            return settings.get(setting_key) if settings else None
        except Exception as e:
            self.logger.error(f"Error getting tenant settings: {e}")
            return None

class EmailProvider(BaseProvider):
    async def send_email(self, to_email: str, subject: str, message: str, tenant_id: int) -> bool:
        """Send email using tenant SMTP settings"""
        try:
            # Get SMTP settings from database
            smtp_host = self._get_tenant_settings(tenant_id, "smtp_host")
            smtp_port = int(self._get_tenant_settings(tenant_id, "smtp_port") or 587)
            smtp_username = self._get_tenant_settings(tenant_id, "smtp_username")
            smtp_password = self._get_tenant_settings(tenant_id, "smtp_password")
            use_tls = self._get_tenant_settings(tenant_id, "smtp_use_tls") == "true"

            if not all([smtp_host, smtp_username, smtp_password]):
                self.logger.error(f"Missing SMTP configuration for tenant {tenant_id}")
                return False

            # Create email message
            email_message = f"""From: {smtp_username}
To: {to_email}
Subject: {subject}
Content-Type: text/html; charset=utf-8

{message}"""

            # Send email
            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, use_tls=use_tls)
            await smtp.connect()
            await smtp.login(smtp_username, smtp_password)
            await smtp.sendmail(smtp_username, [to_email], email_message.encode('utf-8'))
            await smtp.quit()

            self.logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {e}")
            return False

class SMSProvider(BaseProvider):
    async def send_sms(self, to_phone: str, message: str, tenant_id: int) -> bool:
        """Send SMS using tenant SMS provider settings"""
        try:
            # In a real implementation, integrate with services like Twilio, etc.
            sms_provider = self._get_tenant_settings(tenant_id, "sms_provider")
            sms_api_key = self._get_tenant_settings(tenant_id, "sms_api_key")
            sms_sender_id = self._get_tenant_settings(tenant_id, "sms_sender_id")

            if not all([sms_provider, sms_api_key]):
                self.logger.error(f"Missing SMS configuration for tenant {tenant_id}")
                return False

            # Mock implementation - replace with actual SMS service integration
            self.logger.info(f"[MOCK SMS] To: {to_phone}, Message: {message}")
            
            # Simulate API call delay
            import asyncio
            await asyncio.sleep(0.1)
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to send SMS to {to_phone}: {e}")
            return False

class WhatsAppProvider(BaseProvider):
    async def send_whatsapp(self, to_phone: str, message: str, tenant_id: int) -> bool:
        """Send WhatsApp message using tenant WhatsApp provider settings"""
        try:
            whatsapp_provider = self._get_tenant_settings(tenant_id, "whatsapp_provider")
            whatsapp_api_key = self._get_tenant_settings(tenant_id, "whatsapp_api_key")

            if not all([whatsapp_provider, whatsapp_api_key]):
                self.logger.error(f"Missing WhatsApp configuration for tenant {tenant_id}")
                return False

            # Mock implementation - replace with actual WhatsApp service integration
            self.logger.info(f"[MOCK WhatsApp] To: {to_phone}, Message: {message}")
            
            # Simulate API call delay
            import asyncio
            await asyncio.sleep(0.1)
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to send WhatsApp to {to_phone}: {e}")
            return False

class TelegramProvider(BaseProvider):
    async def send_telegram(self, chat_id: str, message: str, tenant_id: int) -> bool:
        """Send Telegram message using tenant Telegram bot settings"""
        try:
            bot_token = self._get_tenant_settings(tenant_id, "telegram_bot_token")

            if not bot_token:
                self.logger.error(f"Missing Telegram configuration for tenant {tenant_id}")
                return False

            # Mock implementation - replace with actual Telegram Bot API
            self.logger.info(f"[MOCK Telegram] To: {chat_id}, Message: {message}")
            
            # Simulate API call delay
            import asyncio
            await asyncio.sleep(0.1)
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to send Telegram to {chat_id}: {e}")
            return False
