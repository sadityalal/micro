from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from .auth_client import AuthClient
from typing import Optional, Dict, Any
import re

security = HTTPBearer()


async def get_tenant_id(request: Request) -> int:
    """Extract tenant ID from request"""
    # Try from JWT token first
    if hasattr(request.state, 'tenant_id'):
        return request.state.tenant_id

    # Try from subdomain
    host = request.headers.get('host', '')
    if host:
        subdomain = host.split('.')[0]
        if subdomain and subdomain not in ['www', 'api', 'localhost']:
            # Map subdomain to tenant ID (you might want to query database)
            tenant_map = {
                'default': 1,
                'tenant1': 2,
                'tenant2': 3
            }
            return tenant_map.get(subdomain, 1)

    # Try from header
    tenant_header = request.headers.get('x-tenant-id')
    if tenant_header and tenant_header.isdigit():
        return int(tenant_header)

    # Default to tenant 1
    return 1


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_client: AuthClient):
        super().__init__(app)
        self.auth_client = auth_client

    async def dispatch(self, request: Request, call_next):
        # Determine tenant ID
        tenant_id = await get_tenant_id(request)
        request.state.tenant_id = tenant_id

        if await self.is_public_endpoint(request):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header missing")

        try:
            credentials = HTTPAuthorizationCredentials(
                scheme=auth_header.split()[0],
                credentials=auth_header.split()[1]
            )
            if credentials.scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")

            user_data = await self.auth_client.verify_token(credentials.credentials, tenant_id)
            if not user_data:
                raise HTTPException(status_code=401, detail="Invalid or expired token")

            request.state.user = user_data
            request.state.user_id = user_data.get("user_id")
            request.state.tenant_id = user_data.get("tenant_id", tenant_id)
            request.state.roles = user_data.get("roles", [])
            request.state.permissions = user_data.get("permissions", [])

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        return await call_next(request)

    async def is_public_endpoint(self, request: Request) -> bool:
        public_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh"
        ]
        return any(request.url.path.startswith(path) for path in public_paths)