"""Redis connection management for notification queue."""
from typing import Optional

import redis
from redis import Redis

from app.core.config import get_settings

settings = get_settings()

_redis_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """Get Redis client instance (singleton pattern)."""
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    if not settings.REDIS_URL:
        return None

    try:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
        )
        _redis_client.ping()
        return _redis_client
    except redis.ConnectionError:
        return None


def close_redis_connection() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
