from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from .auth_client import AuthClient
from typing import Optional, Set
from shared.security.rate_limiter import RateLimitMiddleware
from shared.database.connection import get_redis
from shared.logger import api_gateway_logger
import time

async def get_tenant_id(request: Request) -> int:
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

class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_client: AuthClient, exclude_paths: Optional[Set[str]] = None):
        super().__init__(app)
        self.auth_client = auth_client
        self.rate_limit_middleware = RateLimitMiddleware(get_redis())
        self.exclude_paths = exclude_paths or {
            "/", "/health", "/docs", "/redoc", "/openapi.json",
            "/api/v1/auth/login", "/api/v1/auth/register",
            "/api/v1/auth/refresh", "/api/v1/auth/verify"
        }
        api_gateway_logger.info("AuthenticationMiddleware initialized")

    async def dispatch(self, request: Request, call_next):
        api_gateway_logger.info(f"Middleware processing: {request.method} {request.url.path}")
        
        # Rate limiting
        try:
            await self.rate_limit_middleware.process_request(request)
        except HTTPException as rate_limit_exc:
            return JSONResponse(status_code=rate_limit_exc.status_code, content=rate_limit_exc.detail)

        # Check if path is excluded from authentication
        if any(request.url.path == path or request.url.path.startswith(path + '/') for path in self.exclude_paths):
            api_gateway_logger.info("Path excluded from authentication", extra={"path": request.url.path})
            return await call_next(request)

        # Extract and validate Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            api_gateway_logger.warning("Authorization header missing or invalid")
            return JSONResponse(
                status_code=401, 
                content={"detail": "Authorization header missing or invalid"}
            )

        token = auth_header[7:]  # Remove "Bearer " prefix
        if not token:
            api_gateway_logger.warning("Empty token provided")
            return JSONResponse(
                status_code=401, 
                content={"detail": "Empty token provided"}
            )

        # Get tenant ID
        tenant_id = await get_tenant_id(request)
        api_gateway_logger.info(f"Verifying token for tenant {tenant_id}")

        # Verify token with auth service
        user_data = await self.auth_client.verify_token(token, tenant_id)
        if not user_data:
            api_gateway_logger.warning("Token verification failed")
            return JSONResponse(
                status_code=401, 
                content={"detail": "Invalid or expired token"}
            )

        api_gateway_logger.info(f"Token verified for user {user_data.get('user_id')}")
        
        # Set user data in request state
        request.state.user = user_data
        request.state.user_id = user_data.get("user_id")
        request.state.tenant_id = user_data.get("tenant_id", tenant_id)
        request.state.roles = user_data.get("roles", [])
        request.state.permissions = user_data.get("permissions", [])

        # Process request with authenticated user
        response = await call_next(request)
        return response
