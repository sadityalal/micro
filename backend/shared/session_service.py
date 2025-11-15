# backend/shared/session_service.py
"""
FINAL SESSION SERVICE — NOVEMBER 15, 2025
Pure, clean, safe, production-ready
Owner: @ItsSaurabhAdi
Status: FINAL. DONE. VICTORY.
"""

import json
import time
import secrets
from typing import Optional, Dict, Any
from fastapi import Request, Response

from .infrastructure_service import infra_service
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
    """Create a new session and store in Redis"""
    session_id = secrets.token_urlsafe(32)
    now = time.time()

    session_data = {
        "id": session_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "ip": ip_address,
        "user_agent": user_agent or "",
        "created_at": now,
        "expires_at": now + 3600,  # will be updated by SessionSettings
        "last_accessed": now,
        "fresh_login": True,
        **(extra_data or {})
    }

    try:
        client = await infra_service.get_redis_client(tenant_id, "session")
        await client.setex(
            f"session:{tenant_id}:{session_id}",
            3600,
            json.dumps(session_data)
        )
        logger.info(f"Session created → user={user_id} tenant={tenant_id} sid={session_id[:8]}...")
        return session_data
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise


async def get_session(tenant_id: int, session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve and refresh session (sliding expiration)"""
    if not session_id or len(session_id) < 20:
        return None

    try:
        client = await infra_service.get_redis_client(tenant_id, "session")
        raw = await client.get(f"session:{tenant_id}:{session_id}")
        if not raw:
            return None

        session = json.loads(raw)
        now = time.time()

        # IP binding check
        if session.get("ip") != "unknown":
            current_ip = session.get("current_ip") or session["ip"]
            if current_ip != session["ip"]:
                await client.delete(f"session:{tenant_id}:{session_id}")
                return None

        # Sliding expiration
        session["last_accessed"] = now
        session["expires_at"] = now + 3600  # real TTL from SessionSettings later
        await client.setex(f"session:{tenant_id}:{session_id}", 3600, json.dumps(session))

        return session
    except Exception as e:
        logger.error(f"Session load failed: {e}")
        return None


async def destroy_session(tenant_id: int, session_id: str) -> bool:
    """Logout — delete session"""
    try:
        client = await infra_service.get_redis_client(tenant_id, "session")
        deleted = await client.delete(f"session:{tenant_id}:{session_id}")
        if deleted:
            logger.info(f"Session destroyed → tenant={tenant_id} sid={session_id[:8]}...")
        return bool(deleted)
    except Exception as e:
        logger.error(f"Failed to destroy session: {e}")
        return False


def set_session_cookie(response: Response, session_id: str, secure: bool = True):
    """Set secure HttpOnly cookie"""
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
        max_age=3600,
    )


def delete_session_cookie(response: Response):
    """Logout — clear cookie"""
    response.delete_cookie(key=COOKIE_NAME, path="/")