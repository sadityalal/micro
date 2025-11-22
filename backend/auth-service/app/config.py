import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/pavitra_db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Service Configuration
    AUTH_SERVICE_HOST: str = os.getenv("AUTH_SERVICE_HOST", "0.0.0.0")
    AUTH_SERVICE_PORT: int = int(os.getenv("AUTH_SERVICE_PORT", "8000"))

    # Security Defaults (will be overridden by tenant settings)
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))

    # CORS
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")


settings = Settings()