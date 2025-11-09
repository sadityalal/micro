from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
import logging
from .database import get_redis_connection
from .config import get_settings

logger = logging.getLogger(__name__)


class TenantMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        # Extract tenant from host - this should query tenant service
        host = request.headers.get('host', '')
        tenant_id = await self.extract_tenant_id(host)

        if not tenant_id:
            return JSONResponse(
                status_code=404,
                content={"error": "Tenant not found"}
            )

        # Add tenant to request state
        request.state.tenant_id = tenant_id

        # Get settings for this tenant and add to request state
        request.state.settings = get_settings(tenant_id)

        response = await call_next(request)
        return response

    async def extract_tenant_id(self, host: str) -> int:
        # TODO: Query tenant service to get tenant_id from domain/subdomain
        # For now, return default tenant
        try:
            # This would make an HTTP call to tenant service
            # tenant_id = await tenant_service.get_tenant_id_by_host(host)
            return 1
        except:
            return 1


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        tenant_id = getattr(request.state, 'tenant_id', 1)
        settings = get_settings(tenant_id)
        redis_client = get_redis_connection(tenant_id)

        client_ip = request.client.host

        # Create rate limit key
        minute_key = f"rate_limit:{tenant_id}:{client_ip}:minute"
        hour_key = f"rate_limit:{tenant_id}:{client_ip}:hour"

        # Check minute limit
        minute_count = redis_client.get(minute_key)
        if minute_count and int(minute_count) >= settings.rate_limit_requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again in a minute."}
            )

        # Check hour limit
        hour_count = redis_client.get(hour_key)
        if hour_count and int(hour_count) >= settings.rate_limit_requests_per_hour:
            return JSONResponse(
                status_code=429,
                content={"error": "Hourly rate limit exceeded."}
            )

        # Increment counters
        pipeline = redis_client.pipeline()
        pipeline.incr(minute_key, 1)
        pipeline.expire(minute_key, 60)
        pipeline.incr(hour_key, 1)
        pipeline.expire(hour_key, 3600)
        pipeline.execute()

        response = await call_next(request)
        return response


class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} "
            f"Status: {response.status_code} "
            f"Duration: {process_time:.2f}s"
        )

        return response


# Export all middleware classes
__all__ = ['TenantMiddleware', 'RateLimitMiddleware', 'LoggingMiddleware']