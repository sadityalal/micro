from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..models import User, UserRole, Permission, UserRoleAssignment, RolePermission, Tenant, TenantUser, LoginHistory
from typing import List, Optional, Dict
from datetime import datetime
import ipaddress


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.email == email)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_phone(self, phone: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.phone == phone)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_username(self, username: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.username == username)
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

    def update_user_password(self, user_id: int, new_password_hash: str):
        user = self.get_user_by_id(user_id)
        if user:
            user.password_hash = new_password_hash
            self.db.commit()

    def log_login_attempt(self, login_data: dict):
        # Validate IP address
        try:
            ipaddress.ip_address(login_data.get('ip_address', ''))
        except ValueError:
            login_data['ip_address'] = None

        login_log = LoginHistory(**login_data)
        self.db.add(login_log)
        self.db.commit()

    def get_recent_login_attempts(self, identifier: str, minutes: int = 10) -> int:
        since_time = datetime.utcnow()
        return self.db.query(LoginHistory).filter(
            and_(
                LoginHistory.attempted_email == identifier,
                LoginHistory.login_time >= since_time,
                LoginHistory.status == 'failed'
            )
        ).count()

    def add_to_tenant(self, tenant_id: int, user_id: int, role_id: int):
        tenant_user = TenantUser(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role_id
        )
        self.db.add(tenant_user)
        self.db.commit()