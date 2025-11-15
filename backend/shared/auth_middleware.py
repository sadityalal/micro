# backend/shared/auth_middleware.py
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import asyncio
from .infrastructure_service import infra_service
from .logger_middleware import get_logger

logger = get_logger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

# Secure in-memory cache for JWT secrets (tenant-specific, 5 min TTL)
_jwt_secret_cache: Dict[int, tuple[str, float]] = {}
_cache_lock = asyncio.Lock()


async def get_jwt_secret(tenant_id: int) -> str:
    """Fetch and cache JWT secret per tenant. Never allows weak/default secrets."""
    now = time.time()

    async with _cache_lock:
        if tenant_id in _jwt_secret_cache:
            secret, expiry = _jwt_secret_cache[tenant_id]
            if now < expiry:
                return secret

    try:
        async with infra_service.get_db_session(tenant_id) as db:
            result = await db.execute(
                "SELECT jwt_secret_key FROM security_settings WHERE tenant_id = :tid",
                {"tid": tenant_id}
            )
            row = result.fetchone()
            if not row or not row.jwt_secret_key or len(row.jwt_secret_key.strip()) < 32:
                logger.critical(f"Tenant {tenant_id}: JWT secret missing or too weak")
                raise HTTPException(status_code=500, detail="Authentication system misconfigured")

            secret = row.jwt_secret_key.strip()

            # Block known weak defaults
            if secret in {
                "fallback-secret",
                "your-super-secure-jwt-secret-key-change-in-production",
                "change-me",
                "secret",
                "123456"
            }:
                logger.critical(f"Tenant {tenant_id} using insecure default JWT secret")
                raise HTTPException(status_code=500, detail="Server configuration error")

            async with _cache_lock:
                _jwt_secret_cache[tenant_id] = (secret, now + 300)  # Cache 5 mins
            return secret

    except Exception as e:
        logger.error(f"Failed to load JWT secret for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")


async def _is_token_revoked(jti: str, tenant_id: int) -> bool:
    try:
        redis_client = await infra_service.get_redis_client(tenant_id, "cache")
        return await redis_client.exists(f"revoked_token:{jti}") == 1
    except Exception as e:
        logger.warning(f"Redis unavailable during token revocation check: {e}")
        return False  # Fail open — security vs availability trade-off


class AuthMiddleware:
    def __init__(self):
        self.public_paths = {
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/auth/logout",
        }

    async def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ):
        path = request.url.path

        # Public routes
        if path in self.public_paths or any(path.startswith(p + "/") for p in self.public_paths):
            return
        if path.startswith(("/static/", "/media/", "/assets/", "/favicon")):
            return

        tenant_id = int(request.headers.get("x-tenant-id", "1"))
        request.state.tenant_id = tenant_id

        user = None

        # Try JWT first
        if credentials and credentials.scheme.lower() == "bearer":
            user = await self._validate_jwt(credentials.credentials, tenant_id, request)

        # Fallback: session-based auth (for browser flows)
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

    async def _validate_jwt(self, token: str, tenant_id: int, request: Request) -> Optional[Dict[str, Any]]:
        secret = await get_jwt_secret(tenant_id)
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])

            if payload.get("exp", 0) < time.time():
                return None
            if payload.get("type") != "access":
                return None

            jti = payload.get("jti")
            if jti and await _is_token_revoked(jti, tenant_id):
                logger.info(f"Revoked token used (jti: {jti})")
                return None

            user_id = payload.get("sub")
            if not user_id:
                return None

            return {
                "id": int(user_id),
                "email": payload.get("email"),
                "roles": payload.get("roles", []),
                "auth_type": "jwt",
                "token_jti": jti,
            }

        except JWTError as e:
            logger.debug(f"Invalid JWT token: {e}")
            return None

    async def _validate_session(self, session: dict, tenant_id: int, request: Request) -> Optional[Dict[str, Any]]:
        user_id = session.get("user_id")
        if not user_id:
            return None

        try:
            async with infra_service.get_db_session(tenant_id) as db:
                result = await db.execute(
                    "SELECT id, email, first_name, last_name FROM users WHERE id = :uid",
                    {"uid": user_id}
                )
                user_row = result.fetchone()
                if not user_row:
                    return None

                roles_result = await db.execute(
                    """
                    SELECT r.name 
                    FROM user_roles r 
                    JOIN user_role_assignments ura ON r.id = ura.role_id 
                    WHERE ura.user_id = :uid
                    """,
                    {"uid": user_id}
                )
                roles = [row.name for row in roles_result.fetchall()]

                return {
                    "id": user_row.id,
                    "email": user_row.email,
                    "first_name": user_row.first_name,
                    "last_name": user_row.last_name,
                    "roles": [{"name": r} for r in roles],
                    "auth_type": "session",
                }
        except Exception as e:
            logger.error(f"Session validation failed for user {user_id}: {e}")
            return None


# Singleton instance
auth_middleware = AuthMiddleware()