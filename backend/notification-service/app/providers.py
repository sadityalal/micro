import aiosmtplib
import logging
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from shared.database.repositories.tenant_repository import TenantRepository
from shared.database.connection import get_db
from shared.logger import setup_logger


class BaseProvider:
    def __init__(self):
        self.logger = setup_logger(f"provider-{self.__class__.__name__.lower()}")

    def _get_tenant_settings(self, tenant_id: int, setting_key: str) -> Optional[str]:
        try:
            db = next(get_db())
            from shared.database.models import TenantNotificationSettings
            settings = db.query(TenantNotificationSettings).filter(
                TenantNotificationSettings.tenant_id == tenant_id
            ).all()
            settings_dict = {s.setting_key: s.setting_value for s in settings}
            return settings_dict.get(setting_key)
        except Exception as e:
            self.logger.error(f"Error getting tenant settings: {e}")
            return None


class EmailProvider(BaseProvider):
    async def send_email(self, to_email: str, subject: str, message: str, tenant_id: int) -> bool:
        try:
            smtp_host = self._get_tenant_settings(tenant_id, "smtp_host")
            smtp_port = int(self._get_tenant_settings(tenant_id, "smtp_port") or 587)
            smtp_username = self._get_tenant_settings(tenant_id, "smtp_username")
            smtp_password = self._get_tenant_settings(tenant_id, "smtp_password")
            use_tls = self._get_tenant_settings(tenant_id, "smtp_use_tls") == "true"

            if not all([smtp_host, smtp_username, smtp_password]):
                self.logger.error(f"Missing SMTP configuration for tenant {tenant_id}")
                return False

            email_message = f"""From: {smtp_username}
            To: {to_email}
            Subject: {subject}
            Content-Type: text/html; charset=utf-8
        
            {message}"""

            # For Gmail, we need to use STARTTLS on port 587
            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, use_tls=False)
            await smtp.connect()

            if use_tls:
                await smtp.starttls()

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
        try:
            sms_provider = self._get_tenant_settings(tenant_id, "sms_provider")
            sms_api_key = self._get_tenant_settings(tenant_id, "sms_api_key")
            sms_sender_id = self._get_tenant_settings(tenant_id, "sms_sender_id")

            if not all([sms_provider, sms_api_key, sms_sender_id]):
                self.logger.error(f"Missing SMS configuration for tenant {tenant_id}")
                return False

            # Twilio implementation
            if sms_provider.lower() == 'twilio':
                from twilio.rest import Client
                account_sid = sms_api_key
                auth_token = self._get_tenant_settings(tenant_id, "sms_api_secret")

                client = Client(account_sid, auth_token)
                sms_message = client.messages.create(
                    body=message,
                    from_=sms_sender_id,
                    to=to_phone
                )
                self.logger.info(f"SMS sent via Twilio to {to_phone}, SID: {sms_message.sid}")
                return True

            # Other SMS providers can be added here
            else:
                self.logger.error(f"Unsupported SMS provider: {sms_provider}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to send SMS to {to_phone}: {e}")
            return False


class WhatsAppProvider(BaseProvider):
    async def send_whatsapp(self, to_phone: str, message: str, tenant_id: int) -> bool:
        try:
            whatsapp_provider = self._get_tenant_settings(tenant_id, "whatsapp_provider")
            whatsapp_api_key = self._get_tenant_settings(tenant_id, "whatsapp_api_key")
            whatsapp_api_secret = self._get_tenant_settings(tenant_id, "whatsapp_api_secret")

            if not all([whatsapp_provider, whatsapp_api_key]):
                self.logger.error(f"Missing WhatsApp configuration for tenant {tenant_id}")
                return False

            # Twilio WhatsApp implementation
            if whatsapp_provider.lower() == 'twilio':
                from twilio.rest import Client
                account_sid = whatsapp_api_key
                auth_token = whatsapp_api_secret
                twilio_whatsapp_number = self._get_tenant_settings(tenant_id, "whatsapp_sender_id")

                client = Client(account_sid, auth_token)
                whatsapp_message = client.messages.create(
                    body=message,
                    from_=f'whatsapp:{twilio_whatsapp_number}',
                    to=f'whatsapp:{to_phone}'
                )
                self.logger.info(f"WhatsApp message sent via Twilio to {to_phone}, SID: {whatsapp_message.sid}")
                return True

            # Other WhatsApp providers can be added here
            else:
                self.logger.error(f"Unsupported WhatsApp provider: {whatsapp_provider}")
                return False

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

            if ':' not in bot_token:
                self.logger.error(f"Invalid Telegram bot token format for tenant {tenant_id}")
                return False

            # Handle both usernames (@username) and chat IDs (numeric)
            chat_id = username
            if username.startswith('@'):
                chat_id = username
            else:
                # If it's numeric, use as chat ID directly
                try:
                    int(username)
                    chat_id = username
                except ValueError:
                    self.logger.error(f"Invalid Telegram identifier format: {username}")
                    return False

            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }

            self.logger.info(f"Sending Telegram message to: {chat_id}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(api_url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        self.logger.info(
                            "Telegram message sent successfully",
                            extra={
                                "chat_id": chat_id,
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
                                "chat_id": chat_id,
                                "tenant_id": tenant_id,
                                "error_code": result.get('error_code')
                            }
                        )
                        return False
                else:
                    self.logger.error(
                        f"Telegram API HTTP error: {response.status_code} - {response.text}",
                        extra={
                            "chat_id": chat_id,
                            "tenant_id": tenant_id,
                            "status_code": response.status_code
                        }
                    )
                    return False
        except httpx.TimeoutException:
            self.logger.error(f"Telegram API timeout for chat_id {chat_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send Telegram to {chat_id}: {str(e)}", exc_info=True)
            return False