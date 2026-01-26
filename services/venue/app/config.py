"""
=============================================================================
FILE: config.py
PURPOSE: Configuration management for Venue Service
=============================================================================

Manages all environment variables and settings for the venue service.
Uses pydantic-settings for type-safe configuration with validation.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "FEC Venue Service"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8002

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/venue_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    # Redis (for caching)
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300  # 5 minutes default cache TTL

    # JWT (for validating tokens from Auth Service)
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Service URLs
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8001"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
    ]

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Venue Configuration
    MAX_VENUES_PER_REQUEST: int = 100
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Onboarding
    ONBOARDING_TIMEOUT_HOURS: int = 72  # Auto-expire incomplete onboarding

    # Sync Settings
    CONFIG_SYNC_TIMEOUT_SECONDS: int = 30  # Max time for config sync

    # Feature Flags
    ENABLE_CACHING: bool = True
    ENABLE_RATE_LIMITING: bool = True
    ENABLE_AUDIT_LOGGING: bool = True
    ENABLE_EVENT_PUBLISHING: bool = True

    @property
    def redis_url(self) -> str:
        """Redis URL alias for convenience."""
        return self.REDIS_URL

    @property
    def database_url(self) -> str:
        """Database URL alias."""
        return self.DATABASE_URL

    @property
    def database_pool_size(self) -> int:
        """Pool size alias."""
        return self.DATABASE_POOL_SIZE

    @property
    def database_max_overflow(self) -> int:
        """Max overflow alias."""
        return self.DATABASE_MAX_OVERFLOW

    @property
    def app_name(self) -> str:
        """App name alias."""
        return self.APP_NAME

    @property
    def app_version(self) -> str:
        """Version alias."""
        return self.VERSION

    @property
    def debug(self) -> bool:
        """Debug alias."""
        return self.DEBUG

    @property
    def port(self) -> int:
        """Port alias."""
        return self.PORT

    @property
    def allowed_origins(self) -> List[str]:
        """CORS origins alias."""
        return self.CORS_ORIGINS

    @property
    def sync_database_url(self) -> str:
        """Return synchronous database URL for Alembic migrations."""
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
