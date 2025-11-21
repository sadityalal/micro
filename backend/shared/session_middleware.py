import os
import secrets
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .infrastructure_service import infra_service
from .logger_middleware import get_logger
from .config import get_session_config

logger = get_logger(__name__)


class SecureSessionMiddleware(BaseHTTPMiddleware):
    COOKIE_NAME = "sid"

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        tenant_id = self._get_tenant_id(request)

        try:
            # Get session config from database
            session_config = await get_session_config(tenant_id)
            session_id = request.cookies.get(self.COOKIE_NAME)
            session_data = None

            if session_id and self._is_valid_format(session_id):
                session_data = await self._load_and_refresh_session(
                    tenant_id, session_id, request.client.host, session_config
                )

            request.state.tenant_id = tenant_id
            request.state.session = session_data
            request.state.session_config = session_config

            response = await call_next(request)

            if session_data and session_data.get("fresh_login") and not request.cookies.get(self.COOKIE_NAME):
                self._set_secure_cookie(response, session_data["id"], session_data["expires_at"], session_config)

            return response

        except Exception as e:
            logger.error(f"Session middleware error for tenant {tenant_id}: {e}")
            # Continue without session on error
            request.state.tenant_id = tenant_id
            request.state.session = None
            return await call_next(request)

    def _get_tenant_id(self, request: Request) -> int:
        header = request.headers.get("x-tenant-id")
        return int(header) if header and header.isdigit() else 1

    @staticmethod
    def _is_valid_format(sid: str) -> bool:
        return len(sid) == 43 and all(
            c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in sid)

    async def _load_and_refresh_session(self, tenant_id: int, session_id: str, client_ip: str,
                                        session_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            raw = await client.get(f"session:{tenant_id}:{session_id}")
            if not raw:
                return None

            session = json.loads(raw)
            now = time.time()

            # Use timeout from database config
            session_timeout = session_config.get("session_timeout_minutes", 30) * 60

            if session.get("expires_at", 0) <= now or session.get("ip") != client_ip:
                await client.delete(f"session:{tenant_id}:{session_id}")
                return None

            session["last_accessed"] = now
            session["expires_at"] = now + session_timeout

            await client.setex(f"session:{tenant_id}:{session_id}", session_timeout, json.dumps(session))
            return session

        except Exception as e:
            logger.error(f"Session load failed: {e}")
            return None

    def _set_secure_cookie(self, response: Response, session_id: str, expires_at: float,
                           session_config: Dict[str, Any]):
        secure = session_config.get("secure_cookies", True)
        http_only = session_config.get("http_only_cookies", True)
        same_site = session_config.get("same_site_policy", "lax")
        cookie_path = session_config.get("cookie_path", "/")

        response.set_cookie(
            key=self.COOKIE_NAME,
            value=session_id,
            httponly=http_only,
            secure=secure,
            samesite=same_site,
            expires=datetime.fromtimestamp(expires_at, tz=timezone.utc),
            path=cookie_path,
        )


session_middleware = SecureSessionMiddleware