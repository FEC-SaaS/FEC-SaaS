"""
=============================================================================
FILE: config.py
PURPOSE: API Gateway configuration management
=============================================================================

This module manages all configuration for the API Gateway using Pydantic
settings. Configuration is loaded from environment variables.

CONFIGURATION CATEGORIES:
1. Server Settings - Port, environment, debug mode
2. Service URLs - Backend microservice endpoints
3. Authentication - JWT settings for token validation
4. Rate Limiting - Request throttling configuration
5. CORS - Cross-origin resource sharing settings
6. Timeouts - Request timeout settings

ENVIRONMENT VARIABLES:
All variables are prefixed with GATEWAY_ (e.g., GATEWAY_PORT=8080)

USAGE:
    from app.config import get_settings

    settings = get_settings()
    print(settings.AUTH_SERVICE_URL)

=============================================================================
"""

from functools import lru_cache
from typing import List

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Gateway configuration loaded from environment variables.

    All settings can be overridden via environment variables
    prefixed with GATEWAY_ (e.g., GATEWAY_DEBUG=true).
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_prefix="GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================================================================
    # Server Settings
    # ==========================================================================
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8080
    VERSION: str = "1.0.0"

    # ==========================================================================
    # Backend Service URLs
    # ==========================================================================
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8001"
    VENUE_SERVICE_URL: str = "http://localhost:8002"
    PARTY_SERVICE_URL: str = "http://localhost:8003"
    CUSTOMER_SERVICE_URL: str = "http://localhost:8004"
    MEMBERSHIP_SERVICE_URL: str = "http://localhost:8005"
    BOOKING_SERVICE_URL: str = "http://localhost:8006"
    PAYMENT_SERVICE_URL: str = "http://localhost:8007"
    PAYMENT_GATEWAY_SERVICE_URL: str = "http://localhost:8010"
    ANALYTICS_SERVICE_URL: str = "http://localhost:8008"

    # ==========================================================================
    # Authentication Settings
    # ==========================================================================
    # JWT settings (must match auth service)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Endpoints that don't require authentication
    PUBLIC_PATHS: List[str] = [
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/social/google",
        "/api/v1/auth/social/google/callback",
        "/api/v1/auth/social/facebook",
        "/api/v1/auth/social/callback",
    ]

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "20/minute"
    RATE_LIMIT_SENSITIVE: str = "5/minute"

    # Redis for rate limiting (optional)
    REDIS_URL: str | None = None

    # ==========================================================================
    # CORS Settings
    # ==========================================================================
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://localhost:3001"

    @computed_field
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.CORS_ORIGINS_STR:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",")]

    # ==========================================================================
    # Timeout Settings
    # ==========================================================================
    REQUEST_TIMEOUT: float = 30.0
    CONNECT_TIMEOUT: float = 10.0

    # ==========================================================================
    # Circuit Breaker Settings
    # ==========================================================================
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 30

    # ==========================================================================
    # Logging Settings
    # ==========================================================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Service URL mapping for route resolution
SERVICE_ROUTES = {
    "/api/v1/auth": "AUTH_SERVICE_URL",
    "/api/v1/notifications": "NOTIFICATION_SERVICE_URL",
    "/api/v1/templates": "NOTIFICATION_SERVICE_URL",
    "/api/v1/venues": "VENUE_SERVICE_URL",
    "/api/v1/parties": "PARTY_SERVICE_URL",
    "/api/v1/customers": "CUSTOMER_SERVICE_URL",
    "/api/v1/families": "CUSTOMER_SERVICE_URL",
    "/api/v1/visits": "CUSTOMER_SERVICE_URL",
    "/api/v1/segments": "CUSTOMER_SERVICE_URL",
    "/api/v1/membership": "MEMBERSHIP_SERVICE_URL",
    "/api/v1/bookings": "BOOKING_SERVICE_URL",
    "/api/v1/payments": "PAYMENT_SERVICE_URL",
    "/api/v1/payment-methods": "PAYMENT_GATEWAY_SERVICE_URL",
    "/api/v1/fraud": "PAYMENT_GATEWAY_SERVICE_URL",
    "/api/v1/disputes": "PAYMENT_GATEWAY_SERVICE_URL",
    "/api/v1/analytics": "ANALYTICS_SERVICE_URL",
}


def get_service_url(path: str) -> str | None:
    """
    Get the backend service URL for a given request path.

    Args:
        path: The request path (e.g., /api/v1/auth/login)

    Returns:
        The service URL or None if no matching service
    """
    settings = get_settings()

    for route_prefix, service_attr in SERVICE_ROUTES.items():
        if path.startswith(route_prefix):
            return getattr(settings, service_attr)

    return None


# =============================================================================
# END OF FILE
# =============================================================================
