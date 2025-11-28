from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, update
from ..models import User, UserRole, Permission, UserRoleAssignment, RolePermission, TenantUser, LoginHistory, Address, UserPreferences, UserConsent, DataDeletionRequest
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import ipaddress
import json

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    # User authentication methods
    def get_user_by_email(self, email: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.email == email)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_username(self, username: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.username == username)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_phone(self, phone: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.phone == phone)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_additional_phone(self, phone: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.additional_phone == phone)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_roles(self, user_id: int) -> List[str]:
        roles = (self.db.query(UserRole.name)
                 .join(UserRoleAssignment, UserRoleAssignment.role_id == UserRole.id)
                 .filter(UserRoleAssignment.user_id == user_id)
                 .all())
        return [role[0] for role in roles]

    def get_user_permissions(self, user_id: int) -> List[str]:
        permissions = (self.db.query(Permission.name)
                       .join(RolePermission, RolePermission.permission_id == Permission.id)
                       .join(UserRoleAssignment, UserRoleAssignment.role_id == RolePermission.role_id)
                       .filter(UserRoleAssignment.user_id == user_id)
                       .all())
        return [permission[0] for permission in permissions]

    def create_user(self, user_data: dict) -> User:
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, update_data: dict) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        for key, value in update_data.items():
            setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_password(self, user_id: int, new_password_hash: str):
        user = self.get_user_by_id(user_id)
        if user:
            user.password_hash = new_password_hash
            self.db.commit()

    def log_login_attempt(self, login_data: dict):
        try:
            ipaddress.ip_address(login_data.get('ip_address', ''))
        except ValueError:
            login_data['ip_address'] = None
        login_log = LoginHistory(**login_data)
        self.db.add(login_log)
        self.db.commit()

    def add_to_tenant(self, tenant_id: int, user_id: int, role_id: int):
        tenant_user = TenantUser(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role_id
        )
        self.db.add(tenant_user)
        self.db.commit()

    def get_recent_login_attempts(self, identifier: str, minutes: int = 10) -> int:
        since_time = datetime.utcnow() - timedelta(minutes=minutes)
        return self.db.query(LoginHistory).filter(
            and_(
                LoginHistory.attempted_email == identifier,
                LoginHistory.login_time >= since_time,
                LoginHistory.status == 'failed'
            )
        ).count()

    # Admin functionality methods
    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).offset(skip).limit(limit).all()

    def get_role_by_id(self, role_id: int):
        return self.db.query(UserRole).filter(UserRole.id == role_id).first()

    def assign_role_to_user(self, user_id: int, role_id: int, assigned_by: int):
        # Check if assignment already exists
        existing = self.db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id
        ).first()
        
        if not existing:
            assignment = UserRoleAssignment(
                user_id=user_id,
                role_id=role_id,
                assigned_by=assigned_by
            )
            self.db.add(assignment)
            self.db.commit()

    def get_total_users_count(self) -> int:
        return self.db.query(User).count()

    def get_active_users_count(self) -> int:
        return self.db.query(User).filter(User.is_active == True).count()

    def get_login_attempts_count(self, hours: int = 24) -> int:
        since_time = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(LoginHistory).filter(
            LoginHistory.login_time >= since_time
        ).count()

    def get_failed_login_attempts_count(self, hours: int = 24) -> int:
        since_time = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(LoginHistory).filter(
            LoginHistory.login_time >= since_time,
            LoginHistory.status == 'failed'
        ).count()

    def get_login_history(self, user_id: Optional[int] = None, hours: int = 24, skip: int = 0, limit: int = 100):
        query = self.db.query(LoginHistory)
        
        if user_id:
            query = query.filter(LoginHistory.user_id == user_id)
        
        if hours:
            since_time = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(LoginHistory.login_time >= since_time)
        
        return query.order_by(LoginHistory.login_time.desc()).offset(skip).limit(limit).all()

    # Address management methods
    def create_address(self, user_id: int, address_data: dict) -> Address:
        # If setting as default, unset other defaults
        if address_data.get('is_default'):
            self.db.query(Address).filter(
                Address.user_id == user_id,
                Address.is_default == True
            ).update({'is_default': False})
        
        address = Address(**address_data, user_id=user_id)
        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)
        return address

    def get_user_addresses(self, user_id: int) -> List[Address]:
        return self.db.query(Address).filter(Address.user_id == user_id).all()

    def get_address_by_id(self, address_id: int, user_id: int) -> Optional[Address]:
        return self.db.query(Address).filter(
            Address.id == address_id,
            Address.user_id == user_id
        ).first()

    def update_address(self, address_id: int, user_id: int, update_data: dict) -> Optional[Address]:
        address = self.get_address_by_id(address_id, user_id)
        if not address:
            return None
        
        # If setting as default, unset other defaults
        if update_data.get('is_default'):
            self.db.query(Address).filter(
                Address.user_id == user_id,
                Address.id != address_id,
                Address.is_default == True
            ).update({'is_default': False})
        
        for key, value in update_data.items():
            setattr(address, key, value)
        
        self.db.commit()
        self.db.refresh(address)
        return address

    def delete_address(self, address_id: int, user_id: int) -> bool:
        address = self.get_address_by_id(address_id, user_id)
        if address:
            self.db.delete(address)
            self.db.commit()
            return True
        return False

    def set_default_address(self, address_id: int, user_id: int) -> bool:
        address = self.get_address_by_id(address_id, user_id)
        if not address:
            return False
        
        # Unset all other defaults
        self.db.query(Address).filter(
            Address.user_id == user_id,
            Address.id != address_id,
            Address.is_default == True
        ).update({'is_default': False})
        
        # Set this as default
        address.is_default = True
        self.db.commit()
        return True

    # User preferences and consents
    def get_user_preferences(self, user_id: int) -> Optional[UserPreferences]:
        return self.db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

    def update_user_preferences(self, user_id: int, preferences_data: dict) -> UserPreferences:
        preferences = self.get_user_preferences(user_id)
        if not preferences:
            preferences = UserPreferences(**preferences_data, user_id=user_id)
            self.db.add(preferences)
        else:
            for key, value in preferences_data.items():
                setattr(preferences, key, value)
        
        self.db.commit()
        self.db.refresh(preferences)
        return preferences

    def record_user_consent(self, user_id: int, consent_type: str, granted: bool, version: str, ip_address: str = None):
        consent = UserConsent(
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            version=version,
            ip_address=ip_address
        )
        self.db.add(consent)
        self.db.commit()

    def get_user_consents(self, user_id: int) -> List[UserConsent]:
        return self.db.query(UserConsent).filter(UserConsent.user_id == user_id).all()

    # Data deletion methods
    def create_data_deletion_request(self, user_id: int, deletion_type: str, scheduled_for: datetime, reason: str = None) -> DataDeletionRequest:
        deletion_request = DataDeletionRequest(
            user_id=user_id,
            deletion_type=deletion_type,
            status='pending',
            scheduled_for=scheduled_for,
            reason=reason
        )
        self.db.add(deletion_request)
        self.db.commit()
        self.db.refresh(deletion_request)
        return deletion_request

    def anonymize_user_data(self, user_id: int) -> bool:
        """Anonymize user data for GDPR right to be forgotten"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            # Anonymize personal data but keep account structure
            anonymized_email = f"anon_{user_id}@deleted.example"
            anonymized_name = "Anonymous"
            
            update_data = {
                'first_name': anonymized_name,
                'last_name': anonymized_name,
                'email': anonymized_email,
                'phone': None,
                'username': f"anon_{user_id}",
                'additional_phone': None,
                'telegram_username': None,
                'is_active': False
            }
            
            self.update_user(user_id, update_data)
            
            # Anonymize addresses
            self.db.query(Address).filter(Address.user_id == user_id).update({
                'address_line1': 'Anonymized',
                'address_line2': None,
                'city': 'Anonymized',
                'state': 'Anonymized',
                'country': 'Anonymized',
                'postal_code': '00000'
            })
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            raise e

    def get_pending_deletion_requests(self) -> List[DataDeletionRequest]:
        return self.db.query(DataDeletionRequest).filter(
            DataDeletionRequest.status == 'pending',
            DataDeletionRequest.scheduled_for <= datetime.utcnow()
        ).all()

    def complete_deletion_request(self, request_id: int):
        request = self.db.query(DataDeletionRequest).filter(DataDeletionRequest.id == request_id).first()
        if request:
            request.status = 'completed'
            request.completed_at = datetime.utcnow()
            self.db.commit()

    def get_users_by_role(self, role_names: List[str]) -> List[User]:
        """Get users by role names"""
        return (self.db.query(User)
                .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
                .join(UserRole, UserRole.id == UserRoleAssignment.role_id)
                .filter(UserRole.name.in_(role_names))
                .all())

    def get_tenant_notification_settings(self, tenant_id: int) -> Dict[str, str]:
        """Get notification settings for a tenant"""
        from ..models import TenantNotificationSettings
        settings = self.db.query(TenantNotificationSettings).filter(
            TenantNotificationSettings.tenant_id == tenant_id
        ).all()
        return {setting.setting_key: setting.setting_value for setting in settings}
    def get_user_notification_preferences(self, user_id: int) -> Dict[str, bool]:
        """Get all notification preferences for a user"""
        from ..models import UserNotificationPreference
        preferences = self.db.query(UserNotificationPreference).filter(
            UserNotificationPreference.user_id == user_id
        ).all()
        
        return {pref.notification_method.value: pref.is_enabled for pref in preferences}

    def update_user_notification_preference(self, user_id: int, notification_method: str, is_enabled: bool):
        """Update specific notification preference for a user"""
        from ..models import UserNotificationPreference, NotificationType
        from sqlalchemy.dialects.postgresql import ENUM
        
        # Convert string to enum
        method_enum = NotificationType(notification_method)
        
        preference = self.db.query(UserNotificationPreference).filter(
            UserNotificationPreference.user_id == user_id,
            UserNotificationPreference.notification_method == method_enum
        ).first()
        
        if preference:
            preference.is_enabled = is_enabled
            preference.updated_at = datetime.utcnow()
        else:
            preference = UserNotificationPreference(
                user_id=user_id,
                notification_method=method_enum,
                is_enabled=is_enabled
            )
            self.db.add(preference)
        
        self.db.commit()
        return preference

    def set_user_notification_preferences(self, user_id: int, preferences: Dict[str, bool]):
        """Set multiple notification preferences at once"""
        for method, enabled in preferences.items():
            self.update_user_notification_preference(user_id, method, enabled)

    def get_users_with_notification_enabled(self, notification_method: str, roles: List[str] = None):
        """Get users who have specific notification method enabled, optionally filtered by roles"""
        from ..models import UserNotificationPreference, NotificationType, UserRole, UserRoleAssignment
        
        query = (self.db.query(User)
                .join(UserNotificationPreference, UserNotificationPreference.user_id == User.id)
                .filter(
                    UserNotificationPreference.notification_method == NotificationType(notification_method),
                    UserNotificationPreference.is_enabled == True,
                    User.is_active == True
                ))
        
        if roles:
            query = (query
                    .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
                    .join(UserRole, UserRole.id == UserRoleAssignment.role_id)
                    .filter(UserRole.name.in_(roles)))
        
        return query.all()

    def get_user_telegram_username(self, user_id: int) -> Optional[str]:
        user = self.get_user_by_id(user_id)
        if user and user.telegram_username:
            telegram_id = str(user.telegram_username).strip()
            # If it's numeric, it's a chat ID, otherwise it's a username
            if telegram_id.isdigit():
                return telegram_id  # Return as chat ID
            else:
                # It's a username - ensure it starts with @
                if not telegram_id.startswith('@'):
                    return f"@{telegram_id}"
                return telegram_id
        return None

    def set_default_notification_preferences(self, user_id: int, is_admin: bool = False):
        """Set default notification preferences for a user"""
        from ..models import UserNotificationPreference, NotificationType
        
        # Default preferences based on user type
        if is_admin:
            # Admins get all notifications enabled by default
            default_preferences = {
                NotificationType.email: True,
                NotificationType.sms: True,
                NotificationType.whatsapp: True,
                NotificationType.telegram: True,
                NotificationType.push: True
            }
        else:
            # Regular users get email enabled, others disabled by default
            default_preferences = {
                NotificationType.email: True,
                NotificationType.sms: False,
                NotificationType.whatsapp: False,
                NotificationType.telegram: False,
                NotificationType.push: False
            }
        
        for method, enabled in default_preferences.items():
            preference = UserNotificationPreference(
                user_id=user_id,
                notification_method=method,
                is_enabled=enabled
            )
            self.db.add(preference)
        
        self.db.commit()
        return default_preferences
