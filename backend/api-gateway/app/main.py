from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .auth_client import AuthClient
from .middleware import AuthenticationMiddleware, get_tenant_id
from shared.logger import api_gateway_logger, set_logging_context, generate_request_id, setup_logger
import httpx
import json

def create_app():
    settings_instance = settings
    app = FastAPI(
        title="API Gateway",
        description="Main API Gateway for E-Commerce Platform",
        version="1.0.0"
    )

    # Update logger with database configuration - MUST happen after settings are loaded
    setup_logger("api-gateway", level=settings_instance.LOG_LEVEL)
    
    auth_client = AuthClient(settings_instance.AUTH_SERVICE_URL)
    app.add_middleware(AuthenticationMiddleware, auth_client=auth_client)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings_instance.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = generate_request_id()
        set_logging_context(request_id=request_id)
        api_gateway_logger.info(
            "Request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host
            }
        )
        try:
            response = await call_next(request)
            api_gateway_logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code
                }
            )
            return response
        except Exception as e:
            api_gateway_logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    @app.get("/")
    async def root():
        api_gateway_logger.info("Root endpoint accessed")
        return {"message": "API Gateway is running"}

    @app.get("/health")
    async def health_check():
        api_gateway_logger.info("Health check performed")
        return {"status": "healthy", "service": "api-gateway"}

    # Auth routes
    @app.post("/api/v1/auth/register")
    async def register(request: Request):
        api_gateway_logger.info("Register route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/register",
                content=await request.body(),
                headers=request.headers
            )
            api_gateway_logger.info("Register request forwarded to auth service")
            return response.json()

    @app.post("/api/v1/auth/login")
    async def login(request: Request):
        api_gateway_logger.info("Login route called")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/login",
                    content=await request.body(),
                    headers=request.headers
                )
                api_gateway_logger.info("Login request forwarded to auth service")

                # Handle non-JSON responses gracefully
                if response.status_code != 200:
                    api_gateway_logger.error(f"Auth service returned error: {response.status_code} - {response.text}")
                    return {"error": "Authentication service unavailable", "status_code": response.status_code}

                return response.json()
            except Exception as e:
                api_gateway_logger.error(f"Error calling auth service: {e}")
                return {"error": "Authentication service unavailable", "status_code": 503}

    @app.post("/api/v1/auth/refresh")
    async def refresh_token(request: Request):
        api_gateway_logger.info("Refresh token route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/refresh",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request):
        api_gateway_logger.info("Logout route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/logout",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/auth/verify")
    async def verify_token(request: Request):
        api_gateway_logger.info("Verify token route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/verify",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.get("/api/v1/auth/admin/management")
    async def admin_management_route(request: Request):
        api_gateway_logger.info("Admin management route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/management",
                headers=request.headers
            )
            api_gateway_logger.info("Admin management request forwarded")
            return response.json()

    # Protected route example
    @app.get("/api/v1/protected")
    async def protected_route(request: Request, tenant_id: int = Depends(get_tenant_id)):
        api_gateway_logger.info(
            "Protected route accessed",
            extra={
                "user_id": request.state.user_id,
                "tenant_id": request.state.tenant_id,
                "roles": request.state.roles
            }
        )
        return {
            "message": "This is a protected route",
            "user_id": request.state.user_id,
            "tenant_id": request.state.tenant_id,
            "roles": request.state.roles
        }

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    api_gateway_logger.info("Starting API Gateway")
    uvicorn.run(
        "main:app",
        host=settings.API_GATEWAY_HOST,
        port=settings.API_GATEWAY_PORT,
        reload=True
    )
