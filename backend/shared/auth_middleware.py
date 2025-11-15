# backend/shared/auth_middleware.py
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from functools import lru_cache
import asyncio

from .infrastructure_service import infra_service
from ..logger import get_logger

logger = get_logger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

# Thread-safe cache for JWT secrets
_jwt_secret_cache = {}
_cache_lock = asyncio.Lock()


async def get_jwt_secret(tenant_id: int) -> Optional[str]:
    """Cache JWT secret per tenant with async support"""
    async with _cache_lock:
        if tenant_id in _jwt_secret_cache:
            cached_secret, expiry = _jwt_secret_cache[tenant_id]
            if time.time() < expiry:
                return cached_secret

        try:
            async with infra_service.get_db_session() as db:
                result = await db.execute(
                    "SELECT jwt_secret_key FROM security_settings WHERE tenant_id = :tid",
                    {"tid": tenant_id}
                )
                row = result.fetchone()
                secret = row.jwt_secret_key if row else None

                # Cache for 5 minutes
                if secret:
                    _jwt_secret_cache[tenant_id] = (secret, time.time() + 300)

                return secret
        except Exception as e:
            logger.error(f"Failed to fetch JWT secret for tenant {tenant_id}: {e}")
            return None


class AuthMiddleware:
    def __init__(self):
        self.public_paths = {
            "/health", "/docs", "/redoc", "/openapi.json",
            "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout",
            "/products", "/categories", "/banners", "/pages"
        }

    async def __call__(
            self,
            request: Request,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ):
        # Enhanced public path checking with prefixes
        if self._is_public_route(request):
            return

        tenant_id = getattr(request.state, "tenant_id", 1)
        user = None

        # 1. Try JWT first (API clients, mobile apps)
        if credentials and credentials.scheme.lower() == "bearer":
            user = await self._validate_jwt(credentials.credentials, tenant_id, request)

        # 2. Fallback to session (web browsers)
        if not user:
            session = getattr(request.state, "session", None)
            if session and session.get("user_id"):
                user = await self._validate_session(session, tenant_id, request)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.user = user

    def _is_public_route(self, request: Request) -> bool:
        """Enhanced public route checking"""
        path = request.url.path

        # Exact matches
        if path in self.public_paths:
            return True

        # Prefix matches
        if any(path.startswith(public_path + "/") for public_path in self.public_paths):
            return True

        # Static files
        if path.startswith(("/static/", "/media/", "/assets/")):
            return True

        return False

    async def _validate_jwt(self, token: str, tenant_id: int, request: Request) -> Optional[Dict[str, Any]]:
        secret = await get_jwt_secret(tenant_id)
        if not secret:
            return None

        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])

            # Enhanced token validation
            if payload.get("exp", 0) < time.time():
                logger.debug("JWT token expired")
                return None

            # Validate token type
            if payload.get("type") != "access":
                logger.debug("Invalid JWT token type")
                return None

            # Check token revocation (optional - for enhanced security)
            if await self._is_token_revoked(payload.get("jti"), tenant_id):
                logger.debug("JWT token revoked")
                return None

            user_id = payload.get("sub")
            if not user_id:
                return None

            return {
                "id": int(user_id),
                "email": payload.get("email"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "auth_type": "jwt",
                "token_jti": payload.get("jti")  # For potential revocation
            }

        except JWTError as e:
            logger.debug(f"JWT validation failed: {e}")
            return None
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid user ID in JWT: {e}")
            return None

    async def _validate_session(self, session: dict, tenant_id: int, request: Request) -> Optional[Dict[str, Any]]:
        user_id = session.get("user_id")
        if not user_id:
            return None

        try:
            async with infra_service.get_db_session() as db:
                result = await db.execute(
                    """
                    SELECT u.id, u.email, u.first_name, u.last_name, u.is_active,
                           r.id AS role_id, r.name AS role_name
                    FROM users u
                    LEFT JOIN user_role_assignments ura ON u.id = ura.user_id
                    LEFT JOIN user_roles r ON ura.role_id = r.id
                    WHERE u.id = :uid AND u.tenant_id = :tid AND u.is_active = true
                    """,
                    {"uid": user_id, "tid": tenant_id}
                )
                rows = result.fetchall()
                if not rows:
                    return None

                # Check if user is active
                if not rows[0].is_active:
                    logger.warning(f"Inactive user attempted access: {user_id}")
                    return None

                user = {
                    "id": rows[0].id,
                    "email": rows[0].email,
                    "first_name": rows[0].first_name,
                    "last_name": rows[0].last_name,
                    "is_active": rows[0].is_active,
                    "roles": [
                        {"id": r.role_id, "name": r.role_name}
                        for r in rows if r.role_id
                    ],
                    "permissions": await self._get_permissions(
                        [r.role_id for r in rows if r.role_id]
                    ),
                    "auth_type": "session"
                }
                return user

        except Exception as e:
            logger.error(f"Session auth failed: {e}")
            return None

    async def _get_permissions(self, role_ids: list) -> list:
        if not role_ids:
            return []
        try:
            async with infra_service.get_db_session() as db:
                result = await db.execute(
                    "SELECT DISTINCT p.name, p.module FROM permissions p "
                    "JOIN role_permissions rp ON p.id = rp.permission_id "
                    "WHERE rp.role_id = ANY(:rids)",
                    {"rids": role_ids}
                )
                return [{"name": r.name, "module": r.module} for r in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch permissions: {e}")
            return []

    async def _is_token_revoked(self, token_jti: Optional[str], tenant_id: int) -> bool:
        """Check if JWT token has been revoked (optional enhancement)"""
        if not token_jti:
            return False

        try:
            redis_client = await infra_service.get_redis_client(tenant_id, "cache")
            revoked = await redis_client.get(f"revoked_token:{token_jti}")
            return revoked is not None
        except Exception:
            # If Redis is down, assume token is not revoked (fail open for availability)
            return False


# Global instance
auth_middleware = AuthMiddleware()