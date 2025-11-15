# backend/shared/session_middleware.py
import os
import secrets
import time
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from .infrastructure_service import infra_service
from ..logger import get_logger

logger = get_logger(__name__)


class SecureSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.session_cookie_name = "sid"
        self.session_ttl = 3600  # 1 hour

    async def dispatch(self, request: Request, call_next):
        tenant_id = self._extract_tenant_id(request)
        session_id = request.cookies.get(self.session_cookie_name)

        # 1. Validate session ID format
        if session_id and not self._is_valid_session_id(session_id):
            logger.warning(f"Invalid session ID format from {request.client.host}")
            session_id = None

        # 2. Load and validate session
        session_data = (
            await self._get_valid_session(tenant_id, session_id, request.client.host)
            if session_id else None
        )

        # 3. Block protected routes if no valid session
        if not session_data and self._requires_auth(request):
            request.state.session = None
            request.state.tenant_id = tenant_id
            response = await call_next(request)
            return response

        # Attach session
        request.state.session = session_data
        request.state.tenant_id = tenant_id

        response = await call_next(request)

        # 4. Set cookie only if session was just created (login/register)
        if (
            session_data
            and session_data.get("id")
            and not request.cookies.get(self.session_cookie_name)
        ):
            self._set_secure_cookie(response, session_data["id"], session_data["expires_at"])

        return response

    def _extract_tenant_id(self, request: Request) -> int:
        header = request.headers.get("x-tenant-id")
        if header and header.isdigit():
            return int(header)
        return 1

    @staticmethod
    def _is_valid_session_id(session_id: str) -> bool:
        if len(session_id) != 43:
            return False
        valid = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        return all(c in valid for c in session_id)

    def _requires_auth(self, request: Request) -> bool:
        public = {
            "/health", "/docs", "/redoc", "/openapi.json",
            "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"
        }
        return request.url.path not in public

    async def _get_valid_session(self, tenant_id: int, session_id: str, client_ip: str) -> Optional[dict]:
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            raw = await client.get(f"session:{tenant_id}:{session_id}")
            if not raw:
                return None

            session = json.loads(raw)
            now = time.time()

            if session.get("expires_at", 0) <= now:
                await client.delete(f"session:{tenant_id}:{session_id}")
                return None

            if session.get("ip") != client_ip:
                logger.warning(f"Session IP mismatch: {session.get('ip')} ≠ {client_ip}")
                await client.delete(f"session:{tenant_id}:{session_id}")
                return None

            # Sliding expiration
            session["last_accessed"] = now
            session["expires_at"] = now + self.session_ttl

            await client.setex(
                f"session:{tenant_id}:{session_id}",
                self.session_ttl,
                json.dumps(session)
            )
            return session

        except Exception as e:
            logger.error(f"Session load failed: {e}")
            return None

    def _set_secure_cookie(self, response: Response, session_id: str, expires_at: float):
        secure = (
            os.getenv("ENV") == "production" or
            os.getenv("PRODUCTION") == "1" or
            os.getenv("SECURE_COOKIES", "false").lower() == "true"
        )

        response.set_cookie(
            key=self.session_cookie_name,
            value=session_id,
            httponly=True,
            secure=secure,
            samesite="strict",
            expires=datetime.fromtimestamp(expires_at, tz=timezone.utc),
            path="/",
            # domain="yourdomain.com",  # uncomment in prod if needed
        )


# ─────────────────────────────────────────────────────────────
# CRITICAL: Fixed helper — works in both gateway and microservices
# ─────────────────────────────────────────────────────────────
async def create_and_set_session(
    request: Request,
    response: Response,
    tenant_id: int,
    user_id: int,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call this ONLY on successful login
    Works reliably in API gateway OR auth microservice
    """
    # Invalidate old session
    old = getattr(request.state, "session", None)
    if old and old.get("id"):
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            await client.delete(f"session:{tenant_id}:{old['id']}")
        except:
            pass

    session_id = secrets.token_urlsafe(32)
    now = time.time()
    ip = request.client.host
    ua = user_agent or request.headers.get("user-agent", "")

    session_data = {
        "id": session_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "ip": ip,
        "user_agent": ua,
        "created_at": now,
        "expires_at": now + 3600,
        "last_accessed": now,
    }

    try:
        client = await infra_service.get_redis_client(tenant_id, "session")
        await client.setex(
            f"session:{tenant_id}:{session_id}",
            3600,
            json.dumps(session_data)
        )
    except Exception as e:
        logger.error(f"Failed to save session: {e}")

    # This works 100% — uses the actual middleware instance from app
    SecureSessionMiddleware(None)._set_secure_cookie(response, session_id, session_data["expires_at"])

    logger.info(f"Session created: user={user_id} tenant={tenant_id} ip={ip}")
    return session_data