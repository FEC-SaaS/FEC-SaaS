"""
=============================================================================
FILE: config.py
PURPOSE: Payment Gateway Service configuration settings
=============================================================================
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
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
    app_name: str = Field(default="payment-gateway-service")
    app_version: str = Field(default="0.1.0")
    ENV: str = Field(default="development")
    debug: bool = Field(default=False)
    port: int = Field(default=8010)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/payment_gateway"
    )
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    DATABASE_ECHO: bool = Field(default=False)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/5")

    # RabbitMQ
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")

    # JWT
    jwt_secret_key: str = Field(default="your-secret-key")
    jwt_algorithm: str = Field(default="HS256")

    # Encryption
    encryption_key: str = Field(default="your-32-byte-encryption-key-here")

    # Payment Processors
    stripe_api_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[str] = Field(default=None)
    square_access_token: Optional[str] = Field(default=None)
    square_location_id: Optional[str] = Field(default=None)
    square_environment: str = Field(default="sandbox")

    # Fraud Detection
    fraud_score_threshold: int = Field(default=70)
    fraud_auto_block_threshold: int = Field(default=90)
    velocity_check_window_minutes: int = Field(default=60)
    max_transactions_per_window: int = Field(default=10)

    # PCI Compliance
    pci_compliance_level: str = Field(default="SAQ-A")
    tokenization_enabled: bool = Field(default=True)

    # Service URLs
    auth_service_url: str = Field(default="http://localhost:8000")
    notification_service_url: str = Field(default="http://localhost:8001")
    customer_service_url: str = Field(default="http://localhost:8005")

    # CORS
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"]
    )

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
