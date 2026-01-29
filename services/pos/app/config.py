"""POS Integration Service configuration."""

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
    APP_NAME: str = "FEC POS Integration Service"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8014

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/pos_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/9"

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
    PAYMENT_SERVICE_URL: str = "http://localhost:8007"
    PAYMENT_GATEWAY_SERVICE_URL: str = "http://localhost:8010"
    BOWLING_SERVICE_URL: str = "http://localhost:8013"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
    ]

    # POS defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    DEFAULT_TAX_RATE: float = 0.08
    MAX_REFUND_DAYS: int = 30
    RECEIPT_PREFIX: str = "FEC"
    CASH_DRAWER_VARIANCE_THRESHOLD: float = 5.00
    RECONCILIATION_ALERT_THRESHOLD: float = 100.00
    EXTERNAL_POS_SYNC_INTERVAL_MINUTES: int = 15

    # Stripe Payment Processing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_API_VERSION: str = "2023-10-16"

    # External POS Webhook Secrets
    TOAST_WEBHOOK_SECRET: str = ""
    SQUARE_WEBHOOK_SECRET: str = ""
    CLOVER_WEBHOOK_SECRET: str = ""

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic."""
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
