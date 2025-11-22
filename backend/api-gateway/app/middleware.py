from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from .auth_client import AuthClient
from typing import Optional, Dict, Any
import re

security = HTTPBearer()


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_client: AuthClient):
        super().__init__(app)
        self.auth_client = auth_client

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if await self.is_public_endpoint(request):
            return await call_next(request)

        # Extract token
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

            # Verify token with auth service
            user_data = await self.auth_client.verify_token(credentials.credentials)
            if not user_data:
                raise HTTPException(status_code=401, detail="Invalid or expired token")

            # Add user data to request state
            request.state.user = user_data
            request.state.user_id = user_data.get("user_id")
            request.state.tenant_id = user_data.get("tenant_id")
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