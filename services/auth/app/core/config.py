"""Application configuration loaded from environment variables.

Uses pydantic-settings for type-safe configuration management.
All environment variables should be prefixed with AUTH_ (e.g., AUTH_DATABASE_URL).
"""
from functools import lru_cache
from typing import List

from pydantic import EmailStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    This centralises all configurable settings for the auth service.
    All environment variables use the AUTH_ prefix (e.g., AUTH_REDIS_URL).
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_prefix="AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment settings (AUTH_ENV, AUTH_DEBUG)
    ENV: str = "local"
    DEBUG: bool = False

    PROJECT_NAME: str = "fec-saas-auth-service"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/auth_db"

    # Redis (for token blacklisting / sessions)
    REDIS_URL: str | None = None

    # CORS - stored as string, parsed via computed_field
    BACKEND_CORS_ORIGINS_STR: str = ""

    @computed_field
    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.BACKEND_CORS_ORIGINS_STR:
            return []
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS_STR.split(",")
            if origin.strip()
        ]

    # Email / SMS providers (placeholders for integration services)
    DEFAULT_FROM_EMAIL: EmailStr | None = None

    # Social Auth (optional - configure for OAuth)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    FACEBOOK_APP_ID: str | None = None
    FACEBOOK_APP_SECRET: str | None = None
    APPLE_CLIENT_ID: str | None = None
    APPLE_TEAM_ID: str | None = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()
