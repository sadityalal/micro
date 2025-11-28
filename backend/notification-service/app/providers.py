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
    async def send_telegram(self, username: str, message: str, tenant_id: int) -> bool:
        try:
            bot_token = self._get_tenant_settings(tenant_id, "telegram_bot_token")

            self.logger.info(f"Attempting to send Telegram message to username: {username}")

            if not bot_token or bot_token == "dummy_telegram_token":
                self.logger.error(
                    f"Telegram bot token not configured or still using dummy token for tenant {tenant_id}")
                return False

            # Validate bot token format
            if ':' not in bot_token:
                self.logger.error(f"Invalid Telegram bot token format for tenant {tenant_id}")
                return False

            # Validate username format (should start with @)
            if not username or not username.startswith('@'):
                self.logger.error(f"Invalid Telegram username format: {username}. Should start with @")
                return False

            username_clean = username.strip()

            # Send message via Telegram Bot API
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            payload = {
                "chat_id": username_clean,  # Telegram API accepts usernames as chat_id
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }

            self.logger.info(f"Sending Telegram message to username: {username_clean}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(api_url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        self.logger.info(
                            "Telegram message sent successfully",
                            extra={
                                "username": username_clean,
                                "message_length": len(message),
                                "tenant_id": tenant_id
                            }
                        )
                        return True
                    else:
                        error_desc = result.get('description', 'Unknown error')
                        self.logger.error(
                            f"Telegram API error: {error_desc}",
                            extra={
                                "username": username_clean,
                                "tenant_id": tenant_id,
                                "error_code": result.get('error_code')
                            }
                        )
                        return False
                else:
                    self.logger.error(
                        f"Telegram API HTTP error: {response.status_code} - {response.text}",
                        extra={
                            "username": username_clean,
                            "tenant_id": tenant_id,
                            "status_code": response.status_code
                        }
                    )
                    return False

        except httpx.TimeoutException:
            self.logger.error(f"Telegram API timeout for username {username}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send Telegram to {username}: {str(e)}", exc_info=True)
            return False
