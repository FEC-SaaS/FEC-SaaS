"""Rate limiting middleware using slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()


def _get_client_identifier(request: Request) -> str:
    """Get client identifier for rate limiting.

    Uses X-Forwarded-For if behind proxy, otherwise client IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    return get_remote_address(request)


# Initialize limiter with Redis storage if available, otherwise in-memory
if settings.REDIS_URL:
    from slowapi.util import get_remote_address
    limiter = Limiter(
        key_func=_get_client_identifier,
        storage_uri=settings.REDIS_URL,
        strategy="fixed-window",
    )
else:
    # Fallback to in-memory (not recommended for production)
    limiter = Limiter(
        key_func=_get_client_identifier,
        strategy="fixed-window",
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    # Get rate limit info safely - it may be a tuple or string
    rate_limit_info = "unknown"
    if hasattr(request.state, "view_rate_limit"):
        view_rate_limit = request.state.view_rate_limit
        if isinstance(view_rate_limit, tuple):
            rate_limit_info = str(view_rate_limit[0]) if view_rate_limit else "unknown"
        else:
            rate_limit_info = str(view_rate_limit)

    # Extract retry-after value from exc.detail
    retry_after = "60"  # Default fallback
    if exc.detail:
        # exc.detail might be "Rate limit exceeded: X per Y" format
        retry_after = str(exc.detail).split()[-1] if exc.detail else "60"

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please try again later.",
            "retry_after": str(exc.detail),
        },
        headers={
            "Retry-After": retry_after,
            "X-RateLimit-Limit": rate_limit_info,
        },
    )


# Rate limit decorators for different endpoints
# Usage: @limiter.limit("5/minute")

# Predefined rate limits
RATE_LIMITS = {
    # Authentication endpoints (strict limits)
    "login": "5/minute",
    "register": "3/minute",
    "password_reset": "3/minute",
    "verify_email": "5/minute",

    # Token operations (moderate limits)
    "refresh": "10/minute",
    "logout": "10/minute",

    # User operations (relaxed limits)
    "me": "30/minute",
    "update_profile": "10/minute",

    # Privacy operations
    "export_data": "2/hour",
    "delete_account": "1/hour",

    # General API (default)
    "default": "60/minute",
}


def get_rate_limit(endpoint_name: str) -> str:
    """Get rate limit string for an endpoint."""
    return RATE_LIMITS.get(endpoint_name, RATE_LIMITS["default"])
