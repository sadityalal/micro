import secrets
import time
import json
from typing import Optional, Dict, Any, List
from fastapi import Request, Response
from .infrastructure_service import infra_service
from .logger import get_logger

logger = get_logger(__name__)


class SessionService:
    def __init__(self):
        self.session_cookie_name = "sid"
        self.default_ttl = 3600  # 1 hour

    async def create_session(
            self,
            tenant_id: int,
            user_id: int,
            request: Request,
            user_data: Optional[Dict[str, Any]] = None,
            ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new session for user"""
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        ttl = ttl or self.default_ttl

        session_data = {
            "id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "created_at": now,
            "expires_at": now + ttl,
            "last_accessed": now,
            "user_data": user_data or {}
        }

        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            await client.setex(
                f"session:{tenant_id}:{session_id}",
                ttl,
                json.dumps(session_data)
            )
            logger.info(f"Session created: user={user_id} tenant={tenant_id}")
            return session_data
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def get_session(self, tenant_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by session ID"""
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            raw = await client.get(f"session:{tenant_id}:{session_id}")
            if raw:
                session = json.loads(raw)
                # Update last accessed time
                session["last_accessed"] = time.time()
                await client.setex(
                    f"session:{tenant_id}:{session_id}",
                    int(session["expires_at"] - time.time()),
                    json.dumps(session)
                )
                return session
            return None
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None

    async def update_session(
            self,
            tenant_id: int,
            session_id: str,
            updates: Dict[str, Any]
    ) -> bool:
        """Update session data"""
        try:
            session = await self.get_session(tenant_id, session_id)
            if not session:
                return False

            session.update(updates)
            client = await infra_service.get_redis_client(tenant_id, "session")
            ttl = int(session["expires_at"] - time.time())
            await client.setex(
                f"session:{tenant_id}:{session_id}",
                ttl,
                json.dumps(session)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            return False

    async def delete_session(self, tenant_id: int, session_id: str) -> bool:
        """Delete a session"""
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            result = await client.delete(f"session:{tenant_id}:{session_id}")
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    async def delete_user_sessions(self, tenant_id: int, user_id: int) -> int:
        """Delete all sessions for a user"""
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            pattern = f"session:{tenant_id}:*"
            deleted_count = 0

            # Note: This might be inefficient for large numbers of sessions
            # In production, you might want to maintain a separate index
            async for key in client.scan_iter(match=pattern):
                session_data = await client.get(key)
                if session_data:
                    session = json.loads(session_data)
                    if session.get("user_id") == user_id:
                        await client.delete(key)
                        deleted_count += 1

            logger.info(f"Deleted {deleted_count} sessions for user {user_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete user sessions: {e}")
            return 0

    async def get_user_sessions(self, tenant_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        sessions = []
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            pattern = f"session:{tenant_id}:*"

            async for key in client.scan_iter(match=pattern):
                session_data = await client.get(key)
                if session_data:
                    session = json.loads(session_data)
                    if session.get("user_id") == user_id:
                        sessions.append(session)

            return sessions
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []

    async def cleanup_expired_sessions(self, tenant_id: int) -> int:
        """Clean up expired sessions (Redis handles this automatically with TTL)"""
        # Redis automatically removes expired sessions due to TTL
        # This method is mainly for logging/reporting
        try:
            client = await infra_service.get_redis_client(tenant_id, "session")
            # You could add custom cleanup logic here if needed
            return 0
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0

    async def validate_session_ip(self, session: Dict[str, Any], client_ip: str) -> bool:
        """Validate session IP address"""
        return session.get("ip") == client_ip

    def set_session_cookie(self, response: Response, session_id: str, expires_at: float):
        """Set session cookie on response"""
        import os
        from datetime import datetime, timezone

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
        )

    def clear_session_cookie(self, response: Response):
        """Clear session cookie"""
        response.delete_cookie(
            key=self.session_cookie_name,
            path="/"
        )


# Global session service instance
session_service = SessionService()