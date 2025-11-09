from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

# Import from shared module
from shared.middleware import TenantMiddleware, RateLimitMiddleware, LoggingMiddleware
from shared.database import get_db, get_redis_connection
from shared.config import get_settings
from . import routes


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Auth Service",
    description="Authentication and Authorization Service",
    version="1.0.0"
)

# Add middleware
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/")
async def root():
    return {"message": "Auth Service is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth"}


@app.on_event("startup")
async def startup_event():
    logger.info("Auth Service starting up...")
    # Test database connection
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

    # Test Redis connection
    try:
        redis_client = get_redis_connection()
        redis_client.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)