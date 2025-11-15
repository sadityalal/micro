# backend/shared/rate_limit_middleware.py
"""
FINAL RATE LIMIT MIDDLEWARE — NOVEMBER 15, 2025
100% compatible with:
- infra_service.get_redis_client(tenant_id, "rate_limit")
- Your RateLimitSettings model
- Lua scripts + token bucket + fixed window
"""

import time
from typing import Tuple
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from .infrastructure_service import infra_service
from .models import RateLimitSettings
from .logger_middleware import get_logger

logger = get_logger(__name__)


# ── Lua Scripts (atomic & bulletproof) ─────────────────────────────────────
FIXED_WINDOW_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local count = redis.call("INCR", key)
if count == 1 then redis.call("EXPIRE", key, window) end
if count > limit then return {0, redis.call("TTL", key)} end
return {1, 0}
"""

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local data = redis.call("HMGET", key, "tokens", "last")
local tokens = tonumber(data[1]) or capacity
local last = tonumber(data[2]) or now
local elapsed = now - last
local refill = math.floor(elapsed * rate)
tokens = math.min(capacity, tokens + refill)
if tokens < 1 then
    local wait = math.ceil((1 - tokens) / rate)
    return {0, wait}
end
tokens = tokens - 1
redis.call("HSET", key, "tokens", tokens, "last", now)
redis.call("EXPIRE", key, math.ceil(capacity / rate) + 120)
return {1, 0}
"""


class GlobalRateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._script_shas = {"fixed": None, "token": None}

    async def dispatch(self, request: Request, call_next):
        # Bypass health/docs
        if request.url.path.startswith(("/health", "/metrics", "/docs", "/redoc", "/favicon")):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", 1)
        client_ip = request.client.host
        path_key = request.url.path.split("/", 3)[1] or "root"

        # Load tenant settings from DB
        settings = await self._get_settings(tenant_id)
        if not settings.enabled:
            return await call_next(request)

        identifier = f"rl:{tenant_id}:{client_ip}:{path_key}"
        allowed, retry_after = await self._apply_limit(identifier, settings, tenant_id)

        if not allowed:
            logger.warning(f"RATE LIMIT EXCEEDED → {identifier} | retry_after={retry_after}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers.update({
            "X-RateLimit-Limit": str(settings.requests_per_minute),
            "X-RateLimit-Remaining": "1",
            "X-RateLimit-Reset": str(int(time.time() + 60)),
        })
        return response

    async def _get_settings(self, tenant_id: int) -> RateLimitSettings:
        try:
            async with infra_service.get_db_session(tenant_id) as db:
                result = await db.execute(
                    "SELECT * FROM rate_limit_settings WHERE tenant_id = :tid",
                    {"tid": tenant_id}
                )
                row = result.fetchone()
                if row:
                    return RateLimitSettings(**row._mapping)
        except Exception as e:
            logger.error(f"Failed to load rate limit settings for tenant {tenant_id}: {e}")

        # Secure fallback
        return RateLimitSettings(
            tenant_id=tenant_id,
            strategy="fixed_window",
            requests_per_minute=60,
            burst_capacity=15,
            enabled=True,
        )

    async def _apply_limit(self, key_base: str, settings: RateLimitSettings, tenant_id: int) -> Tuple[bool, int]:
        client = None
        try:
            client = await infra_service.get_redis_client(tenant_id, "rate_limit")
            if not self._script_shas["fixed"]:
                self._script_shas["fixed"] = await client.script_load(FIXED_WINDOW_SCRIPT)
            if not self._script_shas["token"]:
                self._script_shas["token"] = await client.script_load(TOKEN_BUCKET_SCRIPT)
        except Exception as e:
            logger.warning(f"Rate limiter Redis unavailable → allowing request: {e}")
            return True, 0

        strategy = (settings.strategy or "fixed_window").lower()
        now = int(time.time())

        try:
            if strategy == "fixed_window":
                key = f"{key_base}:fw"
                result = await client.evalsha(
                    self._script_shas["fixed"], 1, key, 60, settings.requests_per_minute or 60
                )
                allowed, ttl = result
                return bool(allowed), int(ttl or 60)

            elif strategy == "token_bucket":
                key = f"{key_base}:tb"
                rate = (settings.requests_per_minute or 60) / 60.0
                capacity = settings.burst_capacity or 20
                result = await client.evalsha(
                    self._script_shas["token"], 1, key, now, rate, capacity
                )
                allowed, wait = result
                return bool(allowed), max(1, int(wait))

            else:
                # Fallback to simple counter
                key = f"{key_base}:simple"
                count = await client.incr(key)
                if count == 1:
                    await client.expire(key, 60)
                return count <= (settings.requests_per_minute or 60), 60

        except redis.NoScriptError:
            self._script_shas = {"fixed": None, "token": None}
            return await self._apply_limit(key_base, settings, tenant_id)
        except Exception as e:
            logger.error(f"Rate limit script failed: {e}")
            return True, 0  # Fail open


# Global instance
rate_limiter_middleware = GlobalRateLimiterMiddleware