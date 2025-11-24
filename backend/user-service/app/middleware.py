from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from shared.security.rate_limiter import RateLimitMiddleware
from shared.database.connection import get_redis
from shared.logger import setup_logger, set_logging_context, generate_request_id
import httpx
import redis

class UserAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_service_url: str):
        super().__init__(app)
        self.auth_service_url = auth_service_url
        self.rate_limit_middleware = RateLimitMiddleware(get_redis())
        self.logger = setup_logger("user-service-middleware")

    async def dispatch(self, request: Request, call_next):
        request_id = generate_request_id()
        set_logging_context(request_id=request_id)
        
        # Rate limiting
        try:
            await self.rate_limit_middleware.process_request(request)
        except HTTPException as rate_limit_exc:
            return JSONResponse(status_code=rate_limit_exc.status_code, content=rate_limit_exc.detail)

        # Skip auth for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Extract and validate Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            self.logger.warning("Authorization header missing or invalid")
            return JSONResponse(
                status_code=401, 
                content={"detail": "Authorization header missing or invalid"}
            )

        token = auth_header[7:]
        if not token:
            self.logger.warning("Empty token provided")
            return JSONResponse(
                status_code=401, 
                content={"detail": "Empty token provided"}
            )

        # Verify token with auth service
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.auth_service_url}/api/v1/auth/verify",
                    json={"token": token, "tenant_id": 1},
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    self.logger.warning(f"Token verification failed: {response.status_code}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired token"}
                    )
                
                user_data = response.json()
                request.state.user = user_data
                request.state.user_id = user_data.get("user_id")
                request.state.tenant_id = user_data.get("tenant_id", 1)
                request.state.roles = user_data.get("roles", [])
                request.state.permissions = user_data.get("permissions", [])

        except httpx.TimeoutException:
            self.logger.error("Auth service timeout during token verification")
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service unavailable"}
            )
        except Exception as e:
            self.logger.error(f"Auth service error: {e}")
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service unavailable"}
            )

        # Process request with authenticated user
        response = await call_next(request)
        return response
