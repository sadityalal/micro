from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from shared.database.repositories.user_repository import UserRepository
from shared.database.repositories.tenant_repository import TenantRepository
from shared.schemas.auth import TokenData, Token
import redis
import json


class AuthService:
    def __init__(self, user_repo: UserRepository, tenant_repo: TenantRepository, redis_client: redis.Redis):
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.redis_client = redis_client
        self.ph = PasswordHasher()

    def get_tenant_security_config(self, tenant_id: int) -> Dict[str, Any]:
        """Get security configuration for a tenant"""
        security_settings = self.tenant_repo.get_tenant_security_settings(tenant_id)

        if not security_settings:
            raise Exception(f"Security settings not found for tenant {tenant_id}")

        return {
            "jwt_secret_key": security_settings.jwt_secret_key,
            "jwt_algorithm": security_settings.jwt_algorithm,
            "access_token_expiry_minutes": security_settings.access_token_expiry_minutes,
            "refresh_token_expiry_days": security_settings.refresh_token_expiry_days
        }

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self.ph.verify(hashed_password, plain_password)
        except VerifyMismatchError:
            return False

    def get_password_hash(self, password: str) -> str:
        return self.ph.hash(password)

    # Rest of the methods remain same...
    def authenticate_user(self, login_identifier: str, password: str, tenant_id: Optional[int] = None) -> Optional[
        Dict]:
        """Authenticate user using email, phone, username, or additional_phone"""
        user_repo = self.user_repo
        user = None
        user = user_repo.get_user_by_email(login_identifier, tenant_id)
        if not user:
            user = user_repo.get_user_by_phone(login_identifier, tenant_id)
        if not user:
            user = user_repo.get_user_by_additional_phone(login_identifier, tenant_id)
        if not user:
            user = user_repo.get_user_by_username(login_identifier, tenant_id)
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        roles = user_repo.get_user_roles(user.id)
        permissions = user_repo.get_user_permissions(user.id)
        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "tenant_id": user.tenant_id,
            "roles": roles,
            "permissions": permissions
        }

    def create_access_token(self, data: dict, tenant_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        security_config = self.get_tenant_security_config(tenant_id)

        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=security_config["access_token_expiry_minutes"])

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            security_config["jwt_secret_key"],
            algorithm=security_config["jwt_algorithm"]
        )
        return encoded_jwt

    def create_refresh_token(self, data: dict, tenant_id: int) -> str:
        """Create JWT refresh token"""
        security_config = self.get_tenant_security_config(tenant_id)

        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=security_config["refresh_token_expiry_days"])
        to_encode.update({"exp": expire, "type": "refresh"})

        encoded_jwt = jwt.encode(
            to_encode,
            security_config["jwt_secret_key"],
            algorithm=security_config["jwt_algorithm"]
        )
        return encoded_jwt

    def verify_token(self, token: str, tenant_id: int) -> Optional[TokenData]:
        """Verify JWT token and return token data"""
        try:
            security_config = self.get_tenant_security_config(tenant_id)
            payload = jwt.decode(
                token,
                security_config["jwt_secret_key"],
                algorithms=[security_config["jwt_algorithm"]]
            )

            user_id: int = payload.get("user_id")
            email: str = payload.get("email")
            roles: list = payload.get("roles", [])
            permissions: list = payload.get("permissions", [])
            exp: datetime = datetime.fromtimestamp(payload.get("exp"))

            if user_id is None or email is None:
                return None

            return TokenData(
                user_id=user_id,
                tenant_id=tenant_id,
                email=email,
                roles=roles,
                permissions=permissions,
                exp=exp
            )
        except JWTError:
            return None

    def create_tokens(self, user_data: dict, tenant_id: int) -> Token:
        """Create both access and refresh tokens"""
        token_data = {
            "user_id": user_data["id"],
            "email": user_data["email"],
            "roles": user_data["roles"],
            "permissions": user_data["permissions"],
            "tenant_id": tenant_id
        }

        access_token = self.create_access_token(token_data, tenant_id)
        refresh_token = self.create_refresh_token(token_data, tenant_id)

        # Store refresh token in Redis
        refresh_key = f"refresh_token:{user_data['id']}:{tenant_id}"
        self.redis_client.setex(
            refresh_key,
            timedelta(days=7),  # 7 days expiry for refresh token
            refresh_token
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,  # 1 hour in seconds
            user_id=user_data["id"],
            tenant_id=tenant_id,
            roles=user_data["roles"],
            permissions=user_data["permissions"]
        )

    def revoke_refresh_token(self, user_id: int, tenant_id: int):
        """Revoke refresh token from Redis"""
        refresh_key = f"refresh_token:{user_id}:{tenant_id}"
        self.redis_client.delete(refresh_key)

    def validate_refresh_token(self, refresh_token: str, tenant_id: int) -> Optional[TokenData]:
        """Validate refresh token and return token data"""
        token_data = self.verify_token(refresh_token, tenant_id)
        if not token_data or token_data.user_id is None:
            return None

        # Check if refresh token exists in Redis
        refresh_key = f"refresh_token:{token_data.user_id}:{tenant_id}"
        stored_token = self.redis_client.get(refresh_key)

        if not stored_token or stored_token.decode() != refresh_token:
            return None

        return token_data