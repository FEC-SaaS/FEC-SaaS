"""Application configuration loaded from environment variables.

Uses pydantic-settings for type-safe configuration management.
All environment variables should be prefixed with NOTIFICATION_ (e.g., NOTIFICATION_REDIS_URL).
"""
from functools import lru_cache
from typing import List

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Notification service configuration."""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_prefix="NOTIFICATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENV: str = "local"
    DEBUG: bool = False

    PROJECT_NAME: str = "fec-saas-notification-service"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/notification_db"

    # Redis (for queue management)
    REDIS_URL: str = "redis://localhost:6379/1"

    # RabbitMQ (for message queue)
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Email Provider - SendGrid
    SENDGRID_API_KEY: str | None = None
    DEFAULT_FROM_EMAIL: str = "noreply@fec-saas.com"
    DEFAULT_FROM_NAME: str = "FEC SaaS"

    # SMS Provider - Twilio
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_FROM_NUMBER: str | None = None

    # Push Notifications - Firebase
    FIREBASE_PROJECT_ID: str | None = None
    FIREBASE_CREDENTIALS_PATH: str | None = None

    # Queue Settings
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_SECONDS: int = 60
    BATCH_SIZE: int = 100

    # Rate Limits
    EMAIL_RATE_LIMIT_PER_MINUTE: int = 100
    SMS_RATE_LIMIT_PER_MINUTE: int = 50

    # Delivery Settings
    DEFAULT_PRIORITY: str = "MEDIUM"
    URGENT_DELIVERY_TIMEOUT_SECONDS: int = 30

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
