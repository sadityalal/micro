import uuid
import time
import json
import redis
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from shared.logger import setup_logger

class SessionData(BaseModel):
    session_id: str
    user_id: int
    tenant_id: int
    created_at: float
    last_accessed: float
    expires_at: float
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    custom_data: Dict[str, Any] = {}

class SessionManager:
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.logger = setup_logger("session-manager")

    def generate_session_id(self) -> str:
        return f"session_{uuid.uuid4().hex}"

    def create_session(
        self,
        user_id: int,
        tenant_id: int,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        roles: List[str] = None,
        permissions: List[str] = None,
        custom_data: Dict[str, Any] = None,
        ttl: Optional[int] = None
    ) -> SessionData:
        session_id = self.generate_session_id()
        now = time.time()
        expires_at = now + (ttl or self.default_ttl)
        
        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            created_at=now,
            last_accessed=now,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            roles=roles or [],
            permissions=permissions or [],
            custom_data=custom_data or {}
        )
        
        # Store session in Redis
        session_key = f"session:{session_id}"
        self.redis.setex(
            session_key,
            self.default_ttl,
            session_data.json()
        )
        
        # Store user sessions reference
        user_sessions_key = f"user_sessions:{user_id}:{tenant_id}"
        self.redis.sadd(user_sessions_key, session_id)
        self.redis.expire(user_sessions_key, self.default_ttl * 24)  # Keep for 24 hours
        
        self.logger.info(
            "Session created",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "tenant_id": tenant_id
            }
        )
        
        return session_data

    def get_session(self, session_id: str) -> Optional[SessionData]:
        try:
            session_key = f"session:{session_id}"
            session_json = self.redis.get(session_key)
            
            if not session_json:
                return None
            
            session_data = SessionData.parse_raw(session_json)
            
            # Check if session is expired
            if time.time() > session_data.expires_at:
                self.delete_session(session_id)
                return None
            
            # Update last accessed time (sliding expiration)
            session_data.last_accessed = time.time()
            session_data.expires_at = session_data.last_accessed + self.default_ttl
            
            self.redis.setex(
                session_key,
                self.default_ttl,
                session_data.json()
            )
            
            return session_data
            
        except Exception as e:
            self.logger.error(f"Error getting session: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        try:
            session_key = f"session:{session_id}"
            session_json = self.redis.get(session_key)
            
            if session_json:
                session_data = SessionData.parse_raw(session_json)
                user_sessions_key = f"user_sessions:{session_data.user_id}:{session_data.tenant_id}"
                
                # Remove session from user's sessions
                self.redis.srem(user_sessions_key, session_id)
                
                # Delete session data
                self.redis.delete(session_key)
                
                self.logger.info(
                    "Session deleted",
                    extra={
                        "session_id": session_id,
                        "user_id": session_data.user_id
                    }
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting session: {e}")
            return False

    def delete_user_sessions(self, user_id: int, tenant_id: int, exclude_session: Optional[str] = None):
        try:
            user_sessions_key = f"user_sessions:{user_id}:{tenant_id}"
            session_ids = self.redis.smembers(user_sessions_key)
            
            for session_id in session_ids:
                if session_id != exclude_session:
                    self.delete_session(session_id)
            
            self.logger.info(
                "All user sessions deleted",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "sessions_terminated": len(session_ids) - (1 if exclude_session else 0)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error deleting user sessions: {e}")

    def get_active_user_sessions(self, user_id: int, tenant_id: int) -> List[SessionData]:
        try:
            user_sessions_key = f"user_sessions:{user_id}:{tenant_id}"
            session_ids = self.redis.smembers(user_sessions_key)
            
            active_sessions = []
            for session_id in session_ids:
                session_data = self.get_session(session_id)
                if session_data:
                    active_sessions.append(session_data)
            
            return active_sessions
            
        except Exception as e:
            self.logger.error(f"Error getting active sessions: {e}")
            return []

    def cleanup_expired_sessions(self):
        try:
            # This would typically be run as a background task
            # For now, we rely on Redis TTL
            self.logger.info("Session cleanup completed (handled by Redis TTL)")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired sessions: {e}")
