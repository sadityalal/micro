# backend/apigateway/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared import auth_middleware, session_middleware, rate_limiter_middleware, get_logger
from . import routes

logger = get_logger(__name__)

app = FastAPI(title="Pavitra API Gateway", version="1.0.0")

# Secure CORS — change in production!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://app.pavitra.shop",
        "https://admin.pavitra.shop",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

app.add_middleware(rate_limiter_middleware)
app.add_middleware(session_middleware)
app.add_middleware(auth_middleware)
app.include_router(routes.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api_gateway", "timestamp": time.time()}