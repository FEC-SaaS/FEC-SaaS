"""
=============================================================================
FILE: core/rate_limit.py
PURPOSE: Rate limiting per venue for API endpoints
=============================================================================

Provides rate limiting capabilities:
- Per-venue rate limits
- Per-endpoint rate limits
- Sliding window algorithm
- Redis-backed for distributed deployment
"""

import time
from typing import Optional, Tuple
from uuid import UUID

import redis.asyncio as redis
import structlog
from fastapi import Request, HTTPException, status

from app.config import get_settings

logger = structlog.get_logger()


class RateLimitConfig:
    """Rate limit configuration."""

    # Default limits (requests per window)
    DEFAULT_LIMIT = 100
    DEFAULT_WINDOW = 60  # seconds

    # Endpoint-specific limits
    ENDPOINT_LIMITS = {
        # High-frequency endpoints
        "GET:/api/v1/venues": (200, 60),  # 200 per minute
        "GET:/api/v1/venues/{venue_id}": (300, 60),
        "GET:/api/v1/venues/{venue_id}/is-open": (600, 60),  # Higher for status checks

        # Write operations (more restrictive)
        "POST:/api/v1/venues": (20, 60),
        "PUT:/api/v1/venues/{venue_id}": (30, 60),
        "DELETE:/api/v1/venues/{venue_id}": (10, 60),

        # Bulk operations (very restrictive)
        "POST:/api/v1/venues/bulk": (5, 60),
        "PATCH:/api/v1/venues/bulk": (5, 60),

        # Performance endpoints
        "POST:/api/v1/venues/{venue_id}/performance": (60, 60),
        "GET:/api/v1/venues/{venue_id}/performance": (100, 60),
    }

    # Venue tier multipliers
    TIER_MULTIPLIERS = {
        "starter": 1.0,
        "pro": 2.0,
        "enterprise": 5.0,
    }


class RateLimiter:
    """Redis-backed rate limiter."""

    KEY_PREFIX = "rate_limit"

    def __init__(self, redis_url: str = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._client: Optional[redis.Redis] = None
        self.config = RateLimitConfig()

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is None and self.redis_url:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("rate_limiter_connected")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    def _get_key(
        self,
        identifier: str,
        endpoint: str = None,
        venue_id: UUID = None,
    ) -> str:
        """Generate rate limit key."""
        parts = [self.KEY_PREFIX, identifier]
        if venue_id:
            parts.append(f"venue:{venue_id}")
        if endpoint:
            parts.append(endpoint.replace("/", "_").replace("{", "").replace("}", ""))
        return ":".join(parts)

    def _get_limit_for_endpoint(
        self,
        method: str,
        path: str,
        tier: str = None,
    ) -> Tuple[int, int]:
        """Get rate limit and window for endpoint."""
        # Normalize path (remove specific IDs)
        normalized_path = path
        # Replace UUID patterns with placeholder
        import re
        normalized_path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{venue_id}",
            normalized_path,
        )

        endpoint_key = f"{method}:{normalized_path}"

        # Get base limit
        limit, window = self.config.ENDPOINT_LIMITS.get(
            endpoint_key,
            (self.config.DEFAULT_LIMIT, self.config.DEFAULT_WINDOW),
        )

        # Apply tier multiplier
        if tier:
            multiplier = self.config.TIER_MULTIPLIERS.get(tier, 1.0)
            limit = int(limit * multiplier)

        return limit, window

    async def check_rate_limit(
        self,
        identifier: str,
        method: str,
        path: str,
        venue_id: UUID = None,
        tier: str = None,
    ) -> Tuple[bool, dict]:
        """
        Check if request is within rate limit.

        Returns:
            Tuple of (is_allowed, info_dict)
        """
        if not self._client:
            # No Redis, allow all requests
            return True, {}

        limit, window = self._get_limit_for_endpoint(method, path, tier)
        key = self._get_key(identifier, f"{method}:{path}", venue_id)

        try:
            # Sliding window algorithm using sorted sets
            now = time.time()
            window_start = now - window

            pipe = self._client.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiration
            pipe.expire(key, window)

            results = await pipe.execute()
            current_count = results[1]

            remaining = max(0, limit - current_count - 1)
            reset_at = int(now + window)

            info = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_at,
                "window": window,
            }

            if current_count >= limit:
                logger.warning(
                    "rate_limit_exceeded",
                    identifier=identifier,
                    endpoint=f"{method}:{path}",
                    venue_id=str(venue_id) if venue_id else None,
                    limit=limit,
                )
                return False, info

            return True, info

        except Exception as e:
            logger.error("rate_limit_error", error=str(e))
            # On error, allow the request
            return True, {}

    async def get_remaining(
        self,
        identifier: str,
        method: str,
        path: str,
        venue_id: UUID = None,
        tier: str = None,
    ) -> dict:
        """Get remaining rate limit info without incrementing."""
        if not self._client:
            return {}

        limit, window = self._get_limit_for_endpoint(method, path, tier)
        key = self._get_key(identifier, f"{method}:{path}", venue_id)

        try:
            now = time.time()
            window_start = now - window

            # Remove old and count
            await self._client.zremrangebyscore(key, 0, window_start)
            current_count = await self._client.zcard(key)

            return {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset": int(now + window),
                "window": window,
            }
        except Exception:
            return {}


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware for rate limiting.

    Extracts identifier from JWT token or IP address.
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/ready", "/"]:
        return await call_next(request)

    # Get identifier (prefer user_id from JWT, fallback to IP)
    identifier = request.client.host if request.client else "unknown"

    # Get venue_id from path if present
    venue_id = None
    path_parts = request.url.path.split("/")
    for i, part in enumerate(path_parts):
        if part == "venues" and i + 1 < len(path_parts):
            try:
                venue_id = UUID(path_parts[i + 1])
            except ValueError:
                pass
            break

    # Check rate limit
    is_allowed, info = await rate_limiter.check_rate_limit(
        identifier=identifier,
        method=request.method,
        path=request.url.path,
        venue_id=venue_id,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(info.get("limit", 0)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info.get("reset", 0)),
                "Retry-After": str(info.get("window", 60)),
            },
        )

    response = await call_next(request)

    # Add rate limit headers to response
    if info:
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))

    return response
