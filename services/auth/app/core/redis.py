"""Redis connection management for token blacklisting and rate limiting."""
from typing import Optional

import redis
from redis import Redis

_redis_client: Optional[Redis] = None
_connection_attempted: bool = False


def get_redis_client() -> Optional[Redis]:
    """Get Redis client instance (singleton pattern with lazy loading)."""
    global _redis_client, _connection_attempted

    # Return cached client if already connected
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except (redis.ConnectionError, redis.TimeoutError):
            _redis_client = None
            _connection_attempted = False

    # Only attempt connection once per session to avoid repeated failures
    if _connection_attempted:
        return None

    # Import settings lazily to avoid circular imports
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.REDIS_URL:
        _connection_attempted = True
        return None

    try:
        _connection_attempted = True
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        # Test connection
        _redis_client.ping()
        return _redis_client
    except (redis.ConnectionError, redis.TimeoutError, Exception):
        _redis_client = None
        return None


def close_redis_connection() -> None:
    """Close Redis connection on shutdown."""
    global _redis_client, _connection_attempted
    if _redis_client:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None
    _connection_attempted = False


def reset_redis_connection() -> None:
    """Reset connection state to retry connection."""
    global _redis_client, _connection_attempted
    if _redis_client:
        try:
            _redis_client.close()
        except Exception:
            pass
    _redis_client = None
    _connection_attempted = False
