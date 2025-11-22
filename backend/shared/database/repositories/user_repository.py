from sqlalchemy.orm import Session
from ..models import User, UserRole, Permission, UserRoleAssignment, RolePermission, Tenant, TenantUser
from typing import List, Optional, Dict

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

    def get_user_by_additional_phone(self, phone: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.additional_phone == phone)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        return query.first()

    def get_user_by_username(self, username: str, tenant_id: Optional[int] = None) -> Optional[User]:
        query = self.db.query(User).filter(User.username == username)
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

    def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.domain == domain).first()

    def get_tenant_by_id(self, tenant_id: int) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def create_user(self, user_data: dict) -> User:
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_password(self, user_id: int, new_password_hash: str):
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.password_hash = new_password_hash
            self.db.commit()

    def log_login_attempt(self, login_data: dict):
        from ..models import LoginHistory
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

    def get_user_tenant_info(self, user_id: int, tenant_id: int) -> Optional[Dict]:
        tenant_user = (self.db.query(TenantUser)
                      .filter(TenantUser.user_id == user_id, TenantUser.tenant_id == tenant_id)
                      .first())
        if tenant_user:
            return {
                "tenant_id": tenant_user.tenant_id,
                "user_id": tenant_user.user_id,
                "role_id": tenant_user.role_id,
                "joined_at": tenant_user.joined_at
            }
        return None