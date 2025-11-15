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

_jwt_secret_cache: Dict[int, tuple[str, float]] = {}
_cache_lock = asyncio.Lock()


async def get_jwt_secret(tenant_id: int) -> Optional[str]:
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
            if row and row.jwt_secret_key:
                async with _cache_lock:
                    _jwt_secret_cache[tenant_id] = (row.jwt_secret_key, now + 300)
                return row.jwt_secret_key
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
        if self._is_public_route(request):
            return

        tenant_id = getattr(request.state, "tenant_id", 1)
        user = None

        if credentials and credentials.scheme.lower() == "bearer":
            user = await self._validate_jwt(credentials.credentials, tenant_id, request)

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
        path = request.url.path
        if path in self.public_paths:
            return True
        if any(path.startswith(p + "/") for p in self.public_paths):
            return True
        if path.startswith(("/static/", "/media/", "/assets/")):
            return True
        return False

    async def _validate_jwt(self, token: str, tenant_id: int, request: Request) -> Optional[Dict[str, Any]]:
        secret = await get_jwt_secret(tenant_id)
        if not secret:
            return None

        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            if payload.get("exp", 0) < time.time():
                return None
            if payload.get("type") != "access":
                return None

            jti = payload.get("jti")
            if jti and await self._is_token_revoked(jti, tenant_id):
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
                "token_jti": jti
            }
        except JWTError as e:
            logger.debug(f"JWT invalid: {e}")
            return None

    async def _validate_session(self, session: dict, tenant_id: int, request: Request) -> Optional[Dict[str, Any]]:
        user_id = session.get("user_id")
        if not user_id:
            return None
        try:
            async with infra_service.get_db_session(tenant_id) as db:
                # FIXED QUERY
                result = await db.execute(
                    "SELECT id, email, first_name, last_name FROM users WHERE id = :uid",
                    {"uid": user_id}
                )
                user_row = result.fetchone()
                if not user_row:
                    return None

                # FIXED QUERY
                roles_result = await db.execute(
                    "SELECT r.name FROM user_roles r JOIN user_role_assignments ura ON r.id = ura.role_id WHERE ura.user_id = :uid",
                    {"uid": user_id}
                )
                roles = [row.name for row in roles_result.fetchall()]

                return {
                    "id": user_row.id,
                    "email": user_row.email,
                    "first_name": user_row.first_name,
                    "last_name": user_row.last_name,
                    "roles": [{"name": r} for r in roles],
                    "permissions": [],
                    "auth_type": "session"
                }
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return None

    async def _is_token_revoked(self, jti: str, tenant_id: int) -> bool:
        try:
            redis_client = await infra_service.get_redis_client(tenant_id, "cache")
            return await redis_client.exists(f"revoked_token:{jti}")
        except:
            return False


auth_middleware = AuthMiddleware()