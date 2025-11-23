from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from .auth_client import AuthClient
from typing import Optional, Set
import time

security = HTTPBearer(auto_error=False)


async def get_tenant_id(request: Request) -> int:
    # Extract tenant ID from subdomain, header, or default
    host = request.headers.get('host', '')
    if host:
        subdomain = host.split('.')[0]
        if subdomain and subdomain not in ['www', 'api', 'localhost']:
            tenant_map = {'default': 1, 'tenant1': 2, 'tenant2': 3}
            return tenant_map.get(subdomain, 1)

    tenant_header = request.headers.get('x-tenant-id')
    if tenant_header and tenant_header.isdigit():
        return int(tenant_header)

    return 1


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client, max_requests: int = 100, window: int = 60):
        super().__init__(app)
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        tenant_id = await get_tenant_id(request)
        key = f"gateway_rate_limit:{tenant_id}:{client_ip}"

        current = self.redis.get(key)
        if current and int(current) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Too many requests")

        pipe = self.redis.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, self.window)
        pipe.execute()

        return await call_next(request)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_client: AuthClient, exclude_paths: Optional[Set[str]] = None):
        super().__init__(app)
        self.auth_client = auth_client
        self.exclude_paths = exclude_paths or {
            "/health", "/docs", "/redoc", "/openapi.json",
            "/api/v1/auth/login", "/api/v1/auth/register",
            "/api/v1/auth/refresh", "/api/v1/auth/verify"
        }

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for public endpoints
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Extract token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization header missing or invalid")

        token = auth_header[7:]  # Remove "Bearer " prefix
        tenant_id = await get_tenant_id(request)

        # Verify token
        user_data = await self.auth_client.verify_token(token, tenant_id)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Add user data to request state
        request.state.user = user_data
        request.state.user_id = user_data.get("user_id")
        request.state.tenant_id = user_data.get("tenant_id", tenant_id)
        request.state.roles = user_data.get("roles", [])
        request.state.permissions = user_data.get("permissions", [])

        response = await call_next(request)
        return response