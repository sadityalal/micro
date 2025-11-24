from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, update
from ..models import User, UserRole, Permission, UserRoleAssignment, TenantUser, LoginHistory, Address, UserPreferences, UserConsent, DataDeletionRequest
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import ipaddress
import json

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    # ... existing user methods ...

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

    def create_data_deletion_request(self, user_id: int, deletion_type: str, scheduled_for: datetime, reason: str = None) -> DataDeletionRequest:
        deletion_request = DataDeletionRequest(
            user_id=user_id,
            deletion_type=deletion_type,  # 'anonymize', 'full_delete'
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
