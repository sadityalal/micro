from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .middleware import UserAuthMiddleware
from .routes import router as user_router
from shared.database.connection import DatabaseManager
from shared.logger import setup_logger, set_logging_context, generate_request_id

def create_app():
    app = FastAPI(
        title="User Service",
        description="User Management Microservice",
        version="1.0.0"
    )
    
    # Initialize database
    db_manager = DatabaseManager()
    try:
        db_url = settings.DATABASE_URL
        redis_url = settings.REDIS_URL
        db_manager.initialize(db_url, redis_url)
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise
    
    # Setup logger
    setup_logger("user-service", level=settings.LOG_LEVEL)
    
    # Add middleware
    app.add_middleware(
        UserAuthMiddleware,
        auth_service_url="http://auth-service:8000"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = generate_request_id()
        set_logging_context(request_id=request_id)
        
        logger = setup_logger("user-service")
        logger.info(
            "User request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host
            }
        )
        
        try:
            response = await call_next(request)
            logger.info(
                "User request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code
                }
            )
            return response
        except Exception as e:
            logger.error(
                "User request failed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "user-service"}
    
    @app.get("/")
    async def root():
        return {"message": "User Service is running"}
    
    # Include routers
    app.include_router(user_router, prefix="/api/v1/user", tags=["user"])
    
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.USER_SERVICE_HOST,
        port=settings.USER_SERVICE_PORT,
        reload=True
    )
