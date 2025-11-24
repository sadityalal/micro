import httpx
from typing import Optional, Dict, Any
from shared.logger import api_gateway_logger
from shared.database.connection import get_redis
import redis

class AuthClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self.redis_client = get_redis()
        api_gateway_logger.info("AuthClient initialized")

    async def verify_token(self, token: str, tenant_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        try:
            # Check if token is revoked
            revoked_key = f"revoked_token:{token}"
            if self.redis_client.exists(revoked_key):
                api_gateway_logger.warning("Token is revoked, rejecting request")
                return None

            api_gateway_logger.debug("Verifying token with auth service", extra={"tenant_id": tenant_id})
            
            # Make request to auth service
            response = await self.client.post(
                "/api/v1/auth/verify",
                json={"token": token, "tenant_id": tenant_id or 1},
                timeout=10.0
            )

            if response.status_code == 200:
                api_gateway_logger.debug("Token verification successful")
                return response.json()
            else:
                api_gateway_logger.warning(f"Verify token failed: {response.status_code} - {response.text}")
                return None
                
        except httpx.TimeoutException:
            api_gateway_logger.error("Auth service timeout during token verification")
            return None
        except httpx.RequestError as e:
            api_gateway_logger.error(f"Auth service request error: {e}")
            return None
        except Exception as e:
            api_gateway_logger.error(f"Auth client error: {e}")
            return None

    async def close(self):
        await self.client.aclose()
