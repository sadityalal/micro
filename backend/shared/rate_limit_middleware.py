# backend/shared/rate_limit_middleware.py
import time
from typing import Optional, Tuple
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from ..db import async_session
from ..models.tenant import RateLimitSettings
from ..infrastructure_service import infra_service
from ..logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Atomic Lua Scripts (optimized + bulletproof)
# ─────────────────────────────────────────────────────────────
FIXED_WINDOW_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local count = redis.call("INCR", key)
if count == 1 then
    redis.call("EXPIRE", key, window)
end
if count > limit then
    return {0, redis.call("TTL", key)}
end
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
        self.fixed_sha: Optional[str] = None
        self.token_sha: Optional[str] = None

    async def _load_scripts(self, client: redis.Redis):
        """Load Lua scripts once per Redis connection"""
        if not self.fixed_sha:
            self.fixed_sha = await client.script_load(FIXED_WINDOW_SCRIPT)
        if not self.token_sha:
            self.token_sha = await client.script_load(TOKEN_BUCKET_SCRIPT)

    async def dispatch(self, request: Request, call_next):
        # Bypass internal/health endpoints
        if request.url.path.startswith(("/health", "/metrics", "/docs", "/redoc", "/favicon")):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", 1)
        client_ip = request.client.host
        path_key = request.url.path.split("/", 3)[1] or "root"  # e.g. "auth", "product"

        settings = await self._get_settings(tenant_id)
        if not settings.enabled:
            return await call_next(request)

        # Strong, unique, non-guessable key
        identifier = f"rl:{tenant_id}:{client_ip}:{path_key}"

        allowed, retry_after = await self._apply_limit(identifier, settings, tenant_id)

        if not allowed:
            logger.warning(f"Rate limit exceeded: {identifier} | retry_after={retry_after}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after)),
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
            async with async_session() as db:
                result = await db.execute(
                    "SELECT * FROM rate_limit_settings WHERE tenant_id = :tid",
                    {"tid": tenant_id}
                )
                row = result.fetchone()
                if row:
                    return RateLimitSettings(**row._mapping)
        except Exception as e:
            logger.error(f"Failed to load rate limit settings for tenant {tenant_id}: {e}")

        # Secure default
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
            await self._load_scripts(client)
        except Exception as e:
            logger.warning(f"Rate limiter Redis unavailable: {e} → allowing request")
            return True, 0

        strategy = (settings.strategy or "fixed_window").lower()
        now = int(time.time())

        try:
            if strategy == "fixed_window":
                key = f"{key_base}:fw"
                result = await client.evalsha(
                    self.fixed_sha, 1, key, 60, settings.requests_per_minute or 60
                )
                allowed, ttl = result
                return bool(allowed), int(ttl or 60)

            elif strategy == "token_bucket":
                key = f"{key_base}:tb"
                rate = (settings.requests_per_minute or 60) / 60.0
                capacity = settings.burst_capacity or 20
                result = await client.evalsha(
                    self.token_sha, 1, key, now, rate, capacity
                )
                allowed, wait = result
                return bool(allowed), max(1, int(wait or 1))

            else:  # sliding_window fallback
                key = f"{key_base}:sw"
                limit = settings.requests_per_minute or 60
                pipe = client.pipeline()
                pipe.zremrangebyscore(key, "-inf", now - 60)
                pipe.zcard(key)
                pipe.zadd(key, {now: now})
                pipe.expire(key, 120)
                _, count, _, _ = await pipe.execute()
                return count < limit, 1

        except redis.NoScriptError:
            # Script was flushed → reload and retry once
            self.fixed_sha = self.token_sha = None
            await self._load_scripts(client)
            return await self._apply_limit(key_base, settings, tenant_id)

        except Exception as e:
            logger.error(f"Rate limit evaluation failed for {key_base}: {e}")
            return True, 0  # Fail open

        return True, 0