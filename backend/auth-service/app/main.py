from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .endpoints import router as auth_router
from .admin_endpoints import router as admin_router
from shared.database.connection import DatabaseManager
from shared.logger import auth_service_logger, set_logging_context, generate_request_id, setup_logger

def create_app():
    app = FastAPI(
        title="Auth Service",
        description="Authentication and Authorization Microservice",
        version="1.0.0"
    )

    db_manager = DatabaseManager()
    try:
        db_url = settings.DATABASE_URL
        redis_url = settings.REDIS_URL
        db_manager.initialize(db_url, redis_url)
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise

    # Update logger with database configuration - MUST happen after settings are loaded
    setup_logger("auth-service", level=settings.LOG_LEVEL)
    
    settings_instance = settings

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
        auth_service_logger.info(
            "Auth request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host
            }
        )
        try:
            response = await call_next(request)
            auth_service_logger.info(
                "Auth request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code
                }
            )
            return response
        except Exception as e:
            auth_service_logger.error(
                "Auth request failed",
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
        auth_service_logger.info("Auth service root endpoint accessed")
        return {"message": "Auth Service is running"}

    @app.get("/health")
    async def health_check():
        auth_service_logger.info("Auth service health check performed")
        return {"status": "healthy", "service": "auth-service"}

    # Include both auth and admin routers
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
    app.include_router(admin_router, prefix="/api/v1/auth", tags=["admin"])

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    auth_service_logger.info("Starting Auth Service")
    uvicorn.run(
        "main:app",
        host=settings.AUTH_SERVICE_HOST,
        port=settings.AUTH_SERVICE_PORT,
        reload=True
    )
