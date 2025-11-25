import os
import logging
from typing import Tuple, Optional
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from .schemas import NotificationEventType, NotificationType
from shared.logger import setup_logger

class TemplateManager:
    def __init__(self):
        self.logger = setup_logger("template-manager")
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        
        # Default templates for fallback
        self.default_templates = {
            (NotificationEventType.USER_REGISTERED, NotificationType.EMAIL): {
                "subject": "Welcome to {{ tenant_name }}!",
                "template": "email_user_registered.html"
            },
            (NotificationEventType.USER_REGISTERED, NotificationType.SMS): {
                "subject": "",
                "template": "sms_user_registered.txt"
            },
            (NotificationEventType.USER_REGISTERED, NotificationType.WHATSAPP): {
                "subject": "",
                "template": "whatsapp_user_registered.txt"
            },
            (NotificationEventType.USER_REGISTERED, NotificationType.TELEGRAM): {
                "subject": "",
                "template": "telegram_user_registered.txt"
            },
            (NotificationEventType.PASSWORD_RESET, NotificationType.EMAIL): {
                "subject": "Password Reset Request - {{ tenant_name }}",
                "template": "email_password_reset.html"
            },
            (NotificationEventType.PASSWORD_RESET, NotificationType.SMS): {
                "subject": "",
                "template": "sms_password_reset.txt"
            },
            (NotificationEventType.PASSWORD_RESET, NotificationType.WHATSAPP): {
                "subject": "",
                "template": "whatsapp_password_reset.txt"
            },
            (NotificationEventType.PASSWORD_RESET, NotificationType.TELEGRAM): {
                "subject": "",
                "template": "telegram_password_reset.txt"
            },
            (NotificationEventType.FORGOT_PASSWORD_OTP, NotificationType.EMAIL): {
                "subject": "Password Reset OTP - {{ tenant_name }}",
                "template": "email_password_reset.html"
            },
            (NotificationEventType.FORGOT_PASSWORD_OTP, NotificationType.SMS): {
                "subject": "",
                "template": "sms_password_reset.txt"
            },
            (NotificationEventType.LOGIN_OTP, NotificationType.EMAIL): {
                "subject": "Login OTP - {{ tenant_name }}",
                "template": "email_password_reset.html"  # Reuse template
            },
            (NotificationEventType.LOGIN_OTP, NotificationType.SMS): {
                "subject": "",
                "template": "sms_password_reset.txt"  # Reuse template
            }
        }

    def render_template(self, event_type: NotificationEventType, 
                       notification_type: NotificationType, 
                       data: dict, is_admin: bool = False) -> Tuple[str, str]:
        """Render template for given event and notification type"""
        try:
            # Modify event type for admin notifications
            if is_admin and event_type == NotificationEventType.USER_REGISTERED:
                template_key = (NotificationEventType.USER_REGISTERED, notification_type)
                if notification_type == NotificationType.EMAIL:
                    template_info = {
                        "subject": "New User Registration - {{ tenant_name }}",
                        "template": "email_admin_user_registered.html"
                    }
                elif notification_type == NotificationType.SMS:
                    template_info = {
                        "subject": "",
                        "template": "sms_admin_user_registered.txt"
                    }
                else:
                    # For other types, use regular user registration template
                    template_info = self.default_templates.get(template_key)
            else:
                template_key = (event_type, notification_type)
                template_info = self.default_templates.get(template_key)

            if not template_info:
                self.logger.warning(f"No template found for {event_type} - {notification_type}")
                return self._get_fallback_template(event_type, notification_type, data)

            # Load and render template
            template_file = template_info["template"]
            subject_template = template_info["subject"]
            
            try:
                template = self.env.get_template(template_file)
                message_content = template.render(**data)
                
                # Render subject
                if subject_template:
                    subject_env = Environment()
                    subject_template_obj = subject_env.from_string(subject_template)
                    rendered_subject = subject_template_obj.render(**data)
                else:
                    rendered_subject = ""
                
                return rendered_subject, message_content
                
            except TemplateNotFound:
                self.logger.error(f"Template file not found: {template_file}")
                return self._get_fallback_template(event_type, notification_type, data)
                
        except Exception as e:
            self.logger.error(f"Error rendering template: {e}")
            return self._get_fallback_template(event_type, notification_type, data)

    def _get_fallback_template(self, event_type: NotificationEventType, 
                             notification_type: NotificationType, 
                             data: dict) -> Tuple[str, str]:
        """Provide fallback template when specific template is not found"""
        tenant_name = data.get('tenant_name', 'Our Store')
        
        if notification_type == NotificationType.EMAIL:
            subject = f"Notification from {tenant_name}"
            message = f"""
            <html>
            <body>
                <h2>Notification</h2>
                <p>Event: {event_type.value}</p>
                <p>Hello {data.get('user_first_name', 'User')},</p>
                <p>This is a notification from {tenant_name}.</p>
                <p>Timestamp: {data.get('timestamp', '')}</p>
            </body>
            </html>
            """
        else:
            subject = ""
            message = f"Notification from {tenant_name}: {event_type.value}"
        
        return subject, message
