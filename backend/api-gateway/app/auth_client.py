import httpx
from typing import Optional, Dict, Any

class AuthClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def verify_token(self, token: str, tenant_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        try:
            response = await self.client.post(
                "/api/v1/auth/verify",
                json={"token": token, "tenant_id": tenant_id or 1}  # Ensure tenant_id is provided
            )
            if response.status_code == 200:
                return response.json()
            print(f"Verify token failed: {response.status_code} - {response.text}")  # Debug
            return None
        except Exception as e:
            print(f"Auth client error: {e}")  # Debug
            return None

    async def get_user_permissions(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = await self.client.get("/api/v1/auth/me", headers=headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None