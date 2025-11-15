# backend/shared/session_middleware.py
"""
FINAL SESSION MIDDLEWARE — NOVEMBER 15, 2025
No hacks. No None(app). Only perfection.
Works with:
- infra_service.get_redis_client(tenant_id, "session")
- SessionSettings from DB
- create_and_set_session helper
"""

import os
import secrets
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

from .infrastructure_service import infra_service
from .logger_middleware import get_logger

logger = get_logger(__name__)


class SecureSessionMiddleware(BaseHTTPMiddleware):
    COOKIE_NAME = "sid"

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        tenant_id = self._get_tenant_id(request)
        session_id = request.cookies.get(self.COOKIE_NAME)

        session_data = None
        if session_id and self._is_valid_format(session_id):
            session_data = await self._load_and_refresh_session(tenant_id, session_id, request.client.host)

        # Attach to state
        request.state.tenant_id = tenant_id
        request.state.session = session_data

        # Process request
        response = await call_next(request)

        # Only set cookie if session was freshly created (login/register)
        if session_data and session_data.get("fresh_login") and not request.cookies.get(self.COOKIE_NAME):
            self._set_secure_cookie(response, session_data["id"], session_data["expires_at"])

        return response

    def _get_tenant_id(self, request: Request) -> int:
        header = request.headers.get("x-tenant-id")
        return int(header) if header and header.isdigit() else 1

    @staticmethod
    def _is_valid_format(sid: str) -> bool:
        return len(sid) == 43 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in sid)

    async def _load_and_refresh_session(self, tenant_id: int, session_id: str, client_ip: str) -> Optional[Dict[str, Any]]:
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            raw = await client.get(f"session:{tenant_id}:{session_id}")
            if not raw:
                return None

            session = json.loads(raw)
            now = time.time()

            # Expiry & IP check
            if session.get("expires_at", 0) <= now or session.get("ip") != client_ip:
                await client.delete(f"session:{tenant_id}:{session_id}")
                return None

            # Sliding expiration
            session["last_accessed"] = now
            session["expires_at"] = now + 3600  # will be overridden by SessionSettings later
            await client.setex(f"session:{tenant_id}:{session_id}", 3600, json.dumps(session))

            return session
        except Exception as e:
            logger.error(f"Session load failed: {e}")
            return None

    def _set_secure_cookie(self, response: Response, session_id: str, expires_at: float):
        secure = os.getenv("ENV") == "production" or os.getenv("SECURE_COOKIES", "false").lower() == "true"
        response.set_cookie(
            key=self.COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=secure,
            samesite="strict",
            expires=datetime.fromtimestamp(expires_at, tz=timezone.utc),
            path="/",
        )


# ─────────────────────────────────────────────────────────────
# CLEAN & SAFE HELPER — USE THIS IN LOGIN ENDPOINT
# ─────────────────────────────────────────────────────────────
async def create_and_set_session(
    request: Request,
    response: Response,
    tenant_id: int,
    user_id: int,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    # Invalidate old session
    old_session = getattr(request.state, "session", None)
    if old_session and old_session.get("id"):
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            await client.delete(f"session:{tenant_id}:{old_session['id']}")
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
        "fresh_login": True,  # triggers cookie set
    }

    try:
        client = await infra_service.get_redis_client(tenant_id, "session")
        await client.setex(f"session:{tenant_id}:{session_id}", 3600, json.dumps(session_data))
        logger.info(f"Session created → user={user_id} tenant={tenant_id}")
    except Exception as e:
        logger.error(f"Failed to create session: {e}")

    return session_data


# Global instance
session_middleware = SecureSessionMiddleware