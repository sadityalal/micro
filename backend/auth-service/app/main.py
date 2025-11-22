from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings

app = FastAPI(
    title="Auth Service",
    description="Authentication and Authorization Microservice",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Auth Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth-service"}

# MOVE THIS IMPORT TO HERE (after app creation)
from .endpoints import router as auth_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.AUTH_SERVICE_HOST,
        port=settings.AUTH_SERVICE_PORT,
        reload=True
    )