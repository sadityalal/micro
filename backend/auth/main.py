from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared import (
    session_middleware, rate_limiter_middleware,
    get_logger
)
from . import routes

logger = get_logger(__name__)

app = FastAPI(title="Auth Service", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(rate_limiter_middleware)
app.add_middleware(session_middleware)

app.include_router(routes.router, prefix="/auth", tags=["auth"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)