"""Reservation & Capacity Service configuration."""

from functools import lru_cache
from typing import List

from pydantic import Field
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
    APP_NAME: str = "FEC Reservation & Capacity Service"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8012

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/reservation_capacity_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/7"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Service URLs
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8001"
    VENUE_SERVICE_URL: str = "http://localhost:8002"
    CUSTOMER_SERVICE_URL: str = "http://localhost:8004"
    RESTAURANT_SERVICE_URL: str = "http://localhost:8009"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
    ]

    # Reservation defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    HOLD_EXPIRY_MINUTES: int = 5
    DEFAULT_SLOT_DURATION_MINUTES: int = 30
    DEFAULT_BUFFER_PERCENTAGE: float = 10.0
    DEFAULT_OVERBOOKING_PERCENTAGE: float = 5.0
    MIN_ADVANCE_BOOKING_MINUTES: int = 30
    MAX_ADVANCE_BOOKING_DAYS: int = 90

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic."""
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
