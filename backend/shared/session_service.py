import json
import time
import secrets
from typing import Optional, Dict, Any
from fastapi import Request, Response
from .infrastructure_service import infra_service
from .config import get_session_config
from .logger_middleware import get_logger

logger = get_logger(__name__)

COOKIE_NAME = "sid"


async def create_session(
        tenant_id: int,
        user_id: int,
        user_agent: str = "",
        ip_address: str = "unknown",
        extra_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        # Get session config from database
        session_config = await get_session_config(tenant_id)
        session_timeout = session_config.get("session_timeout_minutes", 30) * 60

        session_id = secrets.token_urlsafe(32)
        now = time.time()

        session_data = {
            "id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "ip": ip_address,
            "user_agent": user_agent or "",
            "created_at": now,
            "expires_at": now + session_timeout,
            "last_accessed": now,
            "fresh_login": True,
            **(extra_data or {})
        }

        client = await infra_service.get_redis_client(tenant_id, "session")
        await client.setex(
            f"session:{tenant_id}:{session_id}",
            session_timeout,
            json.dumps(session_data)
        )

        logger.info(f"Session created → user={user_id} tenant={tenant_id} sid={session_id[:8]}...")
        return session_data

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise


async def get_session(tenant_id: int, session_id: str) -> Optional[Dict[str, Any]]:
    if not session_id or len(session_id) < 20:
        return None

    try:
        # Get session config from database
        session_config = await get_session_config(tenant_id)
        session_timeout = session_config.get("session_timeout_minutes", 30) * 60

        client = await infra_service.get_redis_client(tenant_id, "session")
        raw = await client.get(f"session:{tenant_id}:{session_id}")
        if not raw:
            return None

        session = json.loads(raw)
        now = time.time()

        if session.get("ip") != "unknown":
            current_ip = session.get("current_ip") or session["ip"]
            if current_ip != session["ip"]:
                await client.delete(f"session:{tenant_id}:{session_id}")
                return None

        session["last_accessed"] = now
        session["expires_at"] = now + session_timeout

        await client.setex(f"session:{tenant_id}:{session_id}", session_timeout, json.dumps(session))
        return session

    except Exception as e:
        logger.error(f"Session load failed: {e}")
        return None


async def destroy_session(tenant_id: int, session_id: str) -> bool:
    try:
        client = await infra_service.get_redis_client(tenant_id, "session")
        deleted = await client.delete(f"session:{tenant_id}:{session_id}")
        if deleted:
            logger.info(f"Session destroyed → tenant={tenant_id} sid={session_id[:8]}...")
        return bool(deleted)
    except Exception as e:
        logger.error(f"Failed to destroy session: {e}")
        return False


def set_session_cookie(response: Response, session_id: str, tenant_id: int):
    try:
        # Get session config from database for cookie settings
        session_config = get_session_config(tenant_id)
        secure = session_config.get("secure_cookies", True)
        http_only = session_config.get("http_only_cookies", True)
        same_site = session_config.get("same_site_policy", "lax")
        cookie_path = session_config.get("cookie_path", "/")

        response.set_cookie(
            key=COOKIE_NAME,
            value=session_id,
            httponly=http_only,
            secure=secure,
            samesite=same_site,
            path=cookie_path,
            max_age=session_config.get("session_timeout_minutes", 30) * 60,
        )
    except Exception as e:
        logger.error(f"Failed to set session cookie: {e}")
        # Fallback to secure defaults
        response.set_cookie(
            key=COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=1800,
        )


def delete_session_cookie(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")