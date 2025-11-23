from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from shared.database.repositories.user_repository import UserRepository
from shared.database.repositories.tenant_repository import TenantRepository
from shared.schemas.auth import TokenData, Token
import redis
import time


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        now = int(time.time())
        window_key = f"rate_limit:{key}:{now // window_seconds}"

        pipe = self.redis.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds)
        result = pipe.execute()

        request_count = result[0]
        return request_count > max_requests, max_requests - request_count


class AuthService:
    def __init__(self, user_repo: UserRepository, tenant_repo: TenantRepository, redis_client: redis.Redis):
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.redis_client = redis_client
        self.ph = PasswordHasher()
        self.rate_limiter = RateLimiter(redis_client)

    def check_login_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        key = f"login_attempts:{identifier}"
        return self.rate_limiter.is_rate_limited(key, max_requests=5, window_seconds=300)

    def get_tenant_security_config(self, tenant_id: int) -> Dict[str, Any]:
        security_settings = self.tenant_repo.get_tenant_security_settings(tenant_id)
        if not security_settings:
            raise ValueError(f"Security settings not found for tenant {tenant_id}")
        return {
            "jwt_secret_key": security_settings.jwt_secret_key,
            "jwt_algorithm": security_settings.jwt_algorithm,
            "access_token_expiry_minutes": security_settings.access_token_expiry_minutes,
            "refresh_token_expiry_days": security_settings.refresh_token_expiry_days
        }

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self.ph.verify(hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def get_password_hash(self, password: str) -> str:
        return self.ph.hash(password)

    def authenticate_user(self, login_identifier: str, password: str, tenant_id: Optional[int] = None) -> Optional[
        Dict]:
        # Check rate limiting
        is_limited, remaining = self.check_login_rate_limit(login_identifier)
        if is_limited:
            return None

        user_repo = self.user_repo
        user = None

        # Try different identifiers
        for method in [user_repo.get_user_by_email, user_repo.get_user_by_phone,
                       user_repo.get_user_by_additional_phone, user_repo.get_user_by_username]:
            user = method(login_identifier, tenant_id)
            if user:
                break

        if not user:
            return None

        # Verify password
        if not self.verify_password(password, user.password_hash):
            return None

        # Get user roles and permissions
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
        security_config = self.get_tenant_security_config(tenant_id)
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=security_config["access_token_expiry_minutes"])

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        return jwt.encode(
            to_encode,
            security_config["jwt_secret_key"],
            algorithm=security_config["jwt_algorithm"]
        )

    def create_refresh_token(self, data: dict, tenant_id: int) -> str:
        security_config = self.get_tenant_security_config(tenant_id)
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=security_config["refresh_token_expiry_days"])

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        return jwt.encode(
            to_encode,
            security_config["jwt_secret_key"],
            algorithm=security_config["jwt_algorithm"]
        )

    def verify_token(self, token: str, tenant_id: int) -> Optional[TokenData]:
        try:
            security_config = self.get_tenant_security_config(tenant_id)
            payload = jwt.decode(
                token,
                security_config["jwt_secret_key"],
                algorithms=[security_config["jwt_algorithm"]]
            )

            # Check expiration
            exp_timestamp = payload.get("exp")
            if not exp_timestamp or datetime.utcnow().timestamp() > exp_timestamp:
                return None

            # Validate token type
            token_type = payload.get("type")
            if token_type not in ["access", "refresh"]:
                return None

            return TokenData(
                user_id=payload.get("user_id"),
                tenant_id=payload.get("tenant_id", tenant_id),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                exp=datetime.fromtimestamp(exp_timestamp)
            )
        except JWTError:
            return None

    def create_tokens(self, user_data: dict, tenant_id: int) -> Token:
        token_data = {
            "user_id": user_data["id"],
            "email": user_data["email"],
            "roles": user_data["roles"],
            "permissions": user_data["permissions"],
            "tenant_id": tenant_id
        }

        access_token = self.create_access_token(token_data, tenant_id)
        refresh_token = self.create_refresh_token(token_data, tenant_id)

        # Store refresh token in Redis with expiration
        refresh_key = f"refresh_token:{user_data['id']}:{tenant_id}"
        self.redis_client.setex(
            refresh_key,
            timedelta(days=7),
            refresh_token
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,
            user_id=user_data["id"],
            tenant_id=tenant_id,
            roles=user_data["roles"],
            permissions=user_data["permissions"]
        )

    def revoke_refresh_token(self, user_id: int, tenant_id: int):
        refresh_key = f"refresh_token:{user_id}:{tenant_id}"
        self.redis_client.delete(refresh_key)

    def validate_refresh_token(self, refresh_token: str, tenant_id: int) -> Optional[TokenData]:
        token_data = self.verify_token(refresh_token, tenant_id)
        if not token_data or token_data.user_id is None:
            return None

        # Verify refresh token exists in storage
        refresh_key = f"refresh_token:{token_data.user_id}:{tenant_id}"
        stored_token = self.redis_client.get(refresh_key)

        if not stored_token or stored_token != refresh_token:
            return None

        return token_data