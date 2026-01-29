"""
=============================================================================
FILE: config.py
PURPOSE: Configuration settings for Membership Service
=============================================================================
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Service Configuration
    service_name: str = "membership-service"
    environment: str = "development"
    debug: bool = True
    port: int = 8005
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/membership"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "your-super-secret-jwt-key"
    jwt_algorithm: str = "HS256"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # External Services
    payment_gateway_url: str = "http://localhost:8004"
    customer_service_url: str = "http://localhost:8002"

    # Loyalty Program Defaults
    default_points_per_dollar: float = 1.0
    default_points_expiry_days: int = 365
    max_referral_bonus_points: int = 500

    # Subscription Settings
    dunning_max_attempts: int = 4
    dunning_retry_days: List[int] = [3, 5, 7, 10]
    grace_period_days: int = 7
    max_pause_days: int = 90

    # Notification Settings
    notify_days_before_renewal: List[int] = [7, 3, 1]
    notify_on_points_earned: bool = True
    notify_on_tier_change: bool = True


settings = Settings()
