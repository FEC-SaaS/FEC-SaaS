"""Redis-based rate limiting for reservation endpoints."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# In-memory fallback when Redis is unavailable
_memory_store: dict[str, list[float]] = {}


class RateLimiter:
    """Sliding-window rate limiter backed by Redis (with in-memory fallback)."""

    def __init__(self) -> None:
        self._redis = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            await self._redis.ping()
            logger.info("rate_limiter_redis_connected")
        except Exception as e:
            logger.warning("rate_limiter_redis_unavailable_using_memory", error=str(e))
            self._redis = None

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.close()

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check if the request is within rate limits.

        Returns:
            (allowed, remaining) — whether request is allowed and remaining quota.
        """
        now = datetime.now(timezone.utc).timestamp()

        if self._redis:
            return await self._check_redis(key, max_requests, window_seconds, now)
        return self._check_memory(key, max_requests, window_seconds, now)

    async def _check_redis(
        self, key: str, max_requests: int, window_seconds: int, now: float
    ) -> tuple[bool, int]:
        pipe = self._redis.pipeline()
        window_start = now - window_seconds
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        current_count = results[2]
        remaining = max(0, max_requests - current_count)
        allowed = current_count <= max_requests
        if not allowed:
            # Remove the speculative add
            await self._redis.zrem(key, str(now))
        return allowed, remaining

    def _check_memory(
        self, key: str, max_requests: int, window_seconds: int, now: float
    ) -> tuple[bool, int]:
        window_start = now - window_seconds
        if key not in _memory_store:
            _memory_store[key] = []
        _memory_store[key] = [t for t in _memory_store[key] if t > window_start]
        current_count = len(_memory_store[key])
        if current_count >= max_requests:
            return False, 0
        _memory_store[key].append(now)
        return True, max_requests - current_count - 1


rate_limiter = RateLimiter()


# ─── Dependency helpers ──────────────────────────────────────────────────────

async def check_reservation_create_rate(
    request: Request,
    venue_id: Optional[UUID] = None,
) -> None:
    """Rate limit: max 30 reservation creates per venue per minute."""
    if venue_id:
        key = f"ratelimit:reservation:create:venue:{venue_id}"
        allowed, remaining = await rate_limiter.check_rate_limit(key, 30, 60)
        if not allowed:
            logger.warning("rate_limit_exceeded", key=key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many reservation requests. Please try again later.",
                    "retry_after_seconds": 60,
                },
            )


async def check_customer_rate(
    customer_id: Optional[UUID] = None,
) -> None:
    """Rate limit: max 10 reservation creates per customer per minute."""
    if customer_id:
        key = f"ratelimit:reservation:create:customer:{customer_id}"
        allowed, remaining = await rate_limiter.check_rate_limit(key, 10, 60)
        if not allowed:
            logger.warning("rate_limit_exceeded", key=key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests from this customer. Please try again later.",
                    "retry_after_seconds": 60,
                },
            )
