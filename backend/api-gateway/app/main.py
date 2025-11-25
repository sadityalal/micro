from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .auth_client import AuthClient
from .middleware import AuthenticationMiddleware, get_tenant_id
from shared.logger import api_gateway_logger, set_logging_context, generate_request_id, setup_logger
import httpx
import json
import os

def create_app():
    settings_instance = settings
    app = FastAPI(
        title="API Gateway",
        description="Main API Gateway for E-Commerce Platform",
        version="1.0.0"
    )
    
    setup_logger("api-gateway", level=settings_instance.LOG_LEVEL)

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

    auth_client = AuthClient(settings_instance.AUTH_SERVICE_URL)
    app.add_middleware(AuthenticationMiddleware, auth_client=auth_client)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings_instance.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # === HEALTH & ROOT ===
    @app.get("/")
    async def root():
        api_gateway_logger.info("Root endpoint accessed")
        return {"message": "API Gateway is running"}

    @app.get("/health")
    async def health_check():
        api_gateway_logger.info("Health check performed")
        return {"status": "healthy", "service": "api-gateway"}

    # === AUTH SERVICE ROUTES ===
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
                if response.status_code != 200:
                    api_gateway_logger.error(f"Auth service returned error: {response.status_code} - {response.text}")
                    try:
                        error_detail = response.json()
                        return error_detail
                    except:
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
            if response.status_code == 200:
                return {"message": "Successfully logged out"}
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

    # === Admin Routes ===
    @app.get("/api/v1/auth/admin/users")
    async def admin_users_route(request: Request):
        api_gateway_logger.info("Admin users route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/users",
                headers=request.headers,
                params=dict(request.query_params)
            )
            return response.json()

    @app.get("/api/v1/auth/admin/users/{user_id}")
    async def admin_user_details_route(request: Request, user_id: int):
        api_gateway_logger.info(f"Admin user details route called for user {user_id}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/users/{user_id}",
                headers=request.headers
            )
            return response.json()

    @app.put("/api/v1/auth/admin/users/{user_id}")
    async def admin_update_user_route(request: Request, user_id: int):
        api_gateway_logger.info(f"Admin update user route called for user {user_id}")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/users/{user_id}",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/auth/admin/users/{user_id}/roles")
    async def admin_assign_role_route(request: Request, user_id: int):
        api_gateway_logger.info(f"Admin assign role route called for user {user_id}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/users/{user_id}/roles",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.get("/api/v1/auth/admin/stats")
    async def admin_stats_route(request: Request):
        api_gateway_logger.info("Admin stats route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/stats",
                headers=request.headers
            )
            return response.json()

    @app.get("/api/v1/auth/admin/login-history")
    async def admin_login_history_route(request: Request):
        api_gateway_logger.info("Admin login history route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/login-history",
                headers=request.headers,
                params=dict(request.query_params)
            )
            return response.json()

    @app.get("/api/v1/auth/admin/users/{user_id}/sessions")
    async def admin_user_sessions_route(request: Request, user_id: int):
        api_gateway_logger.info(f"Admin user sessions route called for user {user_id}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/users/{user_id}/sessions",
                headers=request.headers
            )
            return response.json()

    @app.delete("/api/v1/auth/admin/users/{user_id}/sessions")
    async def admin_terminate_sessions_route(request: Request, user_id: int):
        api_gateway_logger.info(f"Admin terminate sessions route called for user {user_id}")
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{settings_instance.AUTH_SERVICE_URL}/api/v1/auth/admin/users/{user_id}/sessions",
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

    # === USER SERVICE ROUTES ===
    
    # Profile Management
    @app.get("/api/v1/user/profile")
    async def get_user_profile(request: Request):
        api_gateway_logger.info("Get user profile route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/profile",
                headers=request.headers
            )
            return response.json()

    @app.put("/api/v1/user/profile")
    async def update_user_profile(request: Request):
        api_gateway_logger.info("Update user profile route called")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/profile",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    # Account Security
    @app.put("/api/v1/user/password")
    async def change_password(request: Request):
        api_gateway_logger.info("Change password route called")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/password",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/deactivate")
    async def deactivate_account(request: Request):
        api_gateway_logger.info("Deactivate account route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/deactivate",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/reactivate")
    async def reactivate_account(request: Request):
        api_gateway_logger.info("Reactivate account route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/reactivate",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/delete-account")
    async def request_account_deletion(request: Request):
        api_gateway_logger.info("Request account deletion route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/delete-account",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/cancel-deletion")
    async def cancel_account_deletion(request: Request):
        api_gateway_logger.info("Cancel account deletion route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/cancel-deletion",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    # Address Management
    @app.get("/api/v1/user/addresses")
    async def get_addresses(request: Request):
        api_gateway_logger.info("Get addresses route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/addresses",
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/addresses")
    async def create_address(request: Request):
        api_gateway_logger.info("Create address route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/addresses",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.put("/api/v1/user/addresses/{address_id}")
    async def update_address(request: Request, address_id: int):
        api_gateway_logger.info(f"Update address route called for address_id: {address_id}")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/addresses/{address_id}",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.delete("/api/v1/user/addresses/{address_id}")
    async def delete_address(request: Request, address_id: int):
        api_gateway_logger.info(f"Delete address route called for address_id: {address_id}")
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/addresses/{address_id}",
                headers=request.headers
            )
            return response.json()

    @app.put("/api/v1/user/addresses/{address_id}/default")
    async def set_default_address(request: Request, address_id: int):
        api_gateway_logger.info(f"Set default address route called for address_id: {address_id}")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/addresses/{address_id}/default",
                headers=request.headers
            )
            return response.json()

    # Session Management
    @app.get("/api/v1/user/sessions")
    async def get_sessions(request: Request):
        api_gateway_logger.info("Get sessions route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/sessions",
                headers=request.headers
            )
            return response.json()

    @app.delete("/api/v1/user/sessions/{session_id}")
    async def terminate_session(request: Request, session_id: str):
        api_gateway_logger.info(f"Terminate session route called for session_id: {session_id}")
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/sessions/{session_id}",
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/sessions/terminate-all")
    async def terminate_all_sessions(request: Request):
        api_gateway_logger.info("Terminate all sessions route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/sessions/terminate-all",
                headers=request.headers
            )
            return response.json()

    # Preferences & Consent
    @app.get("/api/v1/user/preferences")
    async def get_preferences(request: Request):
        api_gateway_logger.info("Get preferences route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/preferences",
                headers=request.headers
            )
            return response.json()

    @app.put("/api/v1/user/preferences")
    async def update_preferences(request: Request):
        api_gateway_logger.info("Update preferences route called")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/preferences",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/user/consent")
    async def record_consent(request: Request):
        api_gateway_logger.info("Record consent route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/consent",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.get("/api/v1/user/consents")
    async def get_consents(request: Request):
        api_gateway_logger.info("Get consents route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/consents",
                headers=request.headers
            )
            return response.json()

    # Login History
    @app.get("/api/v1/user/login-history")
    async def get_login_history(request: Request):
        api_gateway_logger.info("Get login history route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/login-history",
                headers=request.headers
            )
            return response.json()

    # Data Export (GDPR)
    @app.get("/api/v1/user/export-data")
    async def export_user_data(request: Request):
        api_gateway_logger.info("Export user data route called")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings_instance.USER_SERVICE_URL}/api/v1/user/export-data",
                headers=request.headers
            )
            return response.json()

    # === PROTECTED ROUTE (for testing) ===
    @app.get("/api/v1/protected")
    async def protected_route(request: Request, tenant_id: int = Depends(get_tenant_id)):
        user_data = getattr(request.state, 'user', {})
        user_id = user_data.get("user_id")
        tenant_id = user_data.get("tenant_id", tenant_id)
        roles = user_data.get("roles", [])
        api_gateway_logger.info(
            "Protected route accessed",
            extra={
                "user_id": user_id,
                "tenant_id": tenant_id,
                "roles": roles
            }
        )
        return {
            "message": "This is a protected route",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "roles": roles
        }

    @app.post("/api/v1/notifications/send")
    async def send_notification(request: Request):
        api_gateway_logger.info("Send notification route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/notifications/user-registered")
    async def notify_user_registered(request: Request):
        api_gateway_logger.info("User registered notification route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.NOTIFICATION_SERVICE_URL}/api/v1/notifications/user-registered",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/notifications/password-reset")
    async def notify_password_reset(request: Request):
        api_gateway_logger.info("Password reset notification route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.NOTIFICATION_SERVICE_URL}/api/v1/notifications/password-reset",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/notifications/forgot-password-otp")
    async def notify_forgot_password_otp(request: Request):
        api_gateway_logger.info("Forgot password OTP notification route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.NOTIFICATION_SERVICE_URL}/api/v1/notifications/forgot-password-otp",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

    @app.post("/api/v1/notifications/login-otp")
    async def notify_login_otp(request: Request):
        api_gateway_logger.info("Login OTP notification route called")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings_instance.NOTIFICATION_SERVICE_URL}/api/v1/notifications/login-otp",
                content=await request.body(),
                headers=request.headers
            )
            return response.json()

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
