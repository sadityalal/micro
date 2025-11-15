from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import httpx
import time
from typing import Dict, Any
import json

from shared import get_logger, require_permission

logger = get_logger(__name__)
router = APIRouter()

# Service endpoints configuration - ONLY AUTH FOR NOW
SERVICE_ENDPOINTS = {
    "auth": "http://auth:8000"
}


async def forward_request(service: str, path: str, request: Request, user_data: Dict[str, Any] = None) -> JSONResponse:
    """Forward request to appropriate microservice"""
    try:
        # Build target URL
        target_url = f"{SERVICE_ENDPOINTS[service]}{path}"

        # Prepare headers (forward relevant headers)
        headers = {}
        for header in ["content-type", "authorization", "x-tenant-id", "user-agent"]:
            if header in request.headers:
                headers[header] = request.headers[header]

        # Add user context if available
        if user_data:
            headers["x-user-id"] = str(user_data.get("id", ""))
            headers["x-user-email"] = user_data.get("email", "")
            headers["x-user-roles"] = json.dumps(user_data.get("roles", []))

        # Read request body
        body = await request.body()

        # Make the request
        async with httpx.AsyncClient(timeout=30.0) as client:
            method = request.method.lower()

            if method == "get":
                response = await client.get(target_url, headers=headers, params=request.query_params)
            elif method == "post":
                response = await client.post(target_url, headers=headers, content=body)
            elif method == "put":
                response = await client.put(target_url, headers=headers, content=body)
            elif method == "delete":
                response = await client.delete(target_url, headers=headers)
            elif method == "patch":
                response = await client.patch(target_url, headers=headers, content=body)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            # Return the response from the microservice
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code,
                headers=dict(response.headers)
            )

    except httpx.ConnectError:
        logger.error(f"Service {service} is unavailable")
        raise HTTPException(status_code=503, detail=f"Service {service} is temporarily unavailable")
    except Exception as e:
        logger.error(f"Error forwarding request to {service}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Auth service routes - ONLY SERVICE WE HAVE
@router.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def auth_proxy(path: str, request: Request):
    """Proxy requests to auth service"""
    full_path = f"/auth/{path}" if path else "/auth"
    return await forward_request("auth", full_path, request)


# Health check route for all services
@router.api_route("/services/{service}/health", methods=["GET"])
async def service_health(service: str, request: Request):
    """Check health of specific service"""
    if service not in SERVICE_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Service not found")

    full_path = "/health"
    return await forward_request(service, full_path, request)


# Root endpoint
@router.get("/")
async def root():
    return {
        "message": "Pavitra API Gateway",
        "status": "running",
        "available_services": list(SERVICE_ENDPOINTS.keys()),
        "timestamp": time.time()
    }