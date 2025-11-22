from fastapi import FastAPI, Request  # Add Request import
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .auth_client import AuthClient
from .middleware import AuthenticationMiddleware

app = FastAPI(
    title="API Gateway",
    description="Main API Gateway for E-Commerce Platform",
    version="1.0.0"
)

# Initialize auth client
auth_client = AuthClient(settings.AUTH_SERVICE_URL)

# Add middleware
app.add_middleware(AuthenticationMiddleware, auth_client=auth_client)

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
    return {"message": "API Gateway is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/api/v1/protected")
async def protected_route(request: Request):  # Now Request is imported
    return {
        "message": "This is a protected route",
        "user_id": request.state.user_id,
        "tenant_id": request.state.tenant_id,
        "roles": request.state.roles
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_GATEWAY_HOST,
        port=settings.API_GATEWAY_PORT,
        reload=True
    )