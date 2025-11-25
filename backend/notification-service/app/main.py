from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager

from .config import settings
from .routes import router as notification_router
from .notification_service import NotificationService
from shared.database.connection import DatabaseManager
from shared.logger import setup_logger, set_logging_context, generate_request_id

# Global notification service instance
notification_service = NotificationService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logger("notification-service", level=settings.LOG_LEVEL)
    logger = setup_logger("notification-service-main")
    
    # Initialize database
    db_manager = DatabaseManager()
    try:
        db_url = settings.DATABASE_URL
        redis_url = settings.REDIS_URL
        db_manager.initialize(db_url, redis_url)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize RabbitMQ and start consumer
    try:
        await notification_service.initialize_rabbitmq()
        logger.info("RabbitMQ initialized successfully")
        
        # Start background consumer
        asyncio.create_task(notification_service.consume_notifications())
        logger.info("Notification consumer started")
        
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ: {e}")
        raise
    
    yield
    
    # Shutdown
    await notification_service.close()
    logger.info("Notification service shutdown complete")

def create_app():
    app = FastAPI(
        title="Notification Service",
        description="Microservice for handling all notifications in the e-commerce platform",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware
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
        
        logger = setup_logger("notification-service")
        logger.info(
            "Notification request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host
            }
        )
        
        try:
            response = await call_next(request)
            logger.info(
                "Notification request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code
                }
            )
            return response
        except Exception as e:
            logger.error(
                "Notification request failed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    # Health check endpoint
    @app.get("/")
    async def root():
        return {"message": "Notification Service is running"}

    # Include routers
    app.include_router(notification_router, prefix="/api/v1/notifications", tags=["notifications"])

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.NOTIFICATION_SERVICE_HOST,
        port=settings.NOTIFICATION_SERVICE_PORT,
        reload=True
    )
