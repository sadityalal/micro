import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    API_GATEWAY_HOST: str = os.getenv("API_GATEWAY_HOST", "0.0.0.0")
    API_GATEWAY_PORT: int = int(os.getenv("API_GATEWAY_PORT", "8080"))
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

settings = Settings()