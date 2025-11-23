import time
import redis
from typing import Optional, Tuple, Dict, Any
from fastapi import HTTPException, Request
from shared.logger import setup_logger

class EnhancedRateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.logger = setup_logger("rate-limiter")

    async def check_rate_limit(
        self, 
        identifier: str, 
        max_requests: int, 
        window_seconds: int,
        request: Optional[Request] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Enhanced rate limiting with multiple strategies
        """
        now = int(time.time())
        window_key = f"rate_limit:{identifier}:{now // window_seconds}"
        
        try:
            pipe = self.redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window_seconds)
            pipe.ttl(window_key)
            result = pipe.execute()
            
            request_count = result[0]
            ttl = result[2]
            
            is_limited = request_count > max_requests
            remaining = max(0, max_requests - request_count)
            reset_time = now + ttl if ttl > 0 else now + window_seconds
            
            rate_limit_info = {
                "limit": max_requests,
                "remaining": remaining,
                "reset": reset_time,
                "window_seconds": window_seconds,
                "identifier": identifier
            }
            
            if is_limited and request:
                self.logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "identifier": identifier,
                        "client_ip": request.client.host,
                        "path": request.url.path,
                        "limit": max_requests,
                        "window": window_seconds
                    }
                )
            
            return is_limited, rate_limit_info
            
        except redis.RedisError as e:
            self.logger.error(f"Redis error in rate limiting: {e}")
            # Fail open - don't block requests if Redis is down
            return False, {"error": "Rate limit service unavailable"}

    async def check_multi_level_rate_limit(
        self,
        identifiers: Dict[str, str],
        limits: Dict[str, Dict[str, int]],
        request: Request
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Multi-level rate limiting (IP, User, Endpoint)
        """
        results = {}
        is_any_limited = False
        
        for level, identifier in identifiers.items():
            if level in limits:
                limit_config = limits[level]
                is_limited, info = await self.check_rate_limit(
                    f"{level}:{identifier}",
                    limit_config["max_requests"],
                    limit_config["window_seconds"],
                    request
                )
                results[level] = info
                if is_limited:
                    is_any_limited = True
        
        return is_any_limited, results


class RateLimitMiddleware:
    def __init__(self, redis_client: redis.Redis):
        self.rate_limiter = EnhancedRateLimiter(redis_client)
        self.logger = setup_logger("rate-limit-middleware")

    async def process_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Process rate limiting for incoming requests
        """
        client_ip = request.client.host
        user_id = getattr(request.state, 'user_id', 'anonymous')
        path = request.url.path
        
        # Define rate limits based on path and user type
        base_limits = {
            "ip": {"max_requests": 100, "window_seconds": 60},
            "user": {"max_requests": 1000, "window_seconds": 3600},
            "endpoint": {"max_requests": 50, "window_seconds": 60}
        }
        
        # Stricter limits for auth endpoints
        if path.startswith("/api/v1/auth"):
            base_limits["ip"]["max_requests"] = 10
            base_limits["endpoint"]["max_requests"] = 5
        
        # Stricter limits for admin endpoints
        if path.startswith("/api/v1/admin"):
            base_limits["ip"]["max_requests"] = 30
            base_limits["user"]["max_requests"] = 100
        
        identifiers = {
            "ip": client_ip,
            "user": str(user_id),
            "endpoint": path
        }
        
        is_limited, rate_info = await self.rate_limiter.check_multi_level_rate_limit(
            identifiers, base_limits, request
        )
        
        if is_limited:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "details": rate_info,
                    "retry_after": rate_info.get('ip', {}).get('reset', 60) - int(time.time())
                }
            )
        
        return rate_info
