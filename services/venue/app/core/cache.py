"""
=============================================================================
FILE: core/cache.py
PURPOSE: Redis caching implementation for venue service
=============================================================================

Provides caching utilities for:
- Venue data caching
- Feature flag caching
- Settings caching
- Performance metrics caching
"""

import json
import hashlib
from datetime import timedelta
from typing import Any, Optional, Callable, TypeVar
from functools import wraps
from uuid import UUID

import redis.asyncio as redis
import structlog

from app.config import get_settings

logger = structlog.get_logger()

T = TypeVar("T")


class CacheManager:
    """Redis cache manager for venue service."""

    def __init__(self, redis_url: str = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is None and self.redis_url:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("redis_connected", url=self.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client."""
        return self._client

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments."""
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.append(
                hashlib.md5(
                    json.dumps(sorted_kwargs, default=str).encode()
                ).hexdigest()[:8]
            )
        return ":".join(key_parts)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._client:
            return None
        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: int = 300,  # 5 minutes default
    ) -> bool:
        """Set value in cache with expiration."""
        if not self._client:
            return False
        try:
            await self._client.set(
                key,
                json.dumps(value, default=str),
                ex=expire,
            )
            return True
        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._client:
            return 0
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning("cache_delete_pattern_error", pattern=pattern, error=str(e))
            return 0

    # -------------------------------------------------------------------------
    # Venue-specific caching methods
    # -------------------------------------------------------------------------

    async def get_venue(self, venue_id: UUID) -> Optional[dict]:
        """Get cached venue data."""
        key = self._make_key("venue", str(venue_id))
        return await self.get(key)

    async def set_venue(self, venue_id: UUID, data: dict, expire: int = 300) -> bool:
        """Cache venue data."""
        key = self._make_key("venue", str(venue_id))
        return await self.set(key, data, expire)

    async def invalidate_venue(self, venue_id: UUID) -> bool:
        """Invalidate venue cache."""
        pattern = f"venue:{venue_id}*"
        deleted = await self.delete_pattern(pattern)
        logger.info("venue_cache_invalidated", venue_id=str(venue_id), keys_deleted=deleted)
        return deleted > 0

    async def get_venue_features(self, venue_id: UUID) -> Optional[list]:
        """Get cached venue features."""
        key = self._make_key("venue", str(venue_id), "features")
        return await self.get(key)

    async def set_venue_features(self, venue_id: UUID, features: list, expire: int = 600) -> bool:
        """Cache venue features (longer TTL)."""
        key = self._make_key("venue", str(venue_id), "features")
        return await self.set(key, features, expire)

    async def get_venue_hours(self, venue_id: UUID) -> Optional[list]:
        """Get cached venue hours."""
        key = self._make_key("venue", str(venue_id), "hours")
        return await self.get(key)

    async def set_venue_hours(self, venue_id: UUID, hours: list, expire: int = 3600) -> bool:
        """Cache venue hours (longer TTL - hours change infrequently)."""
        key = self._make_key("venue", str(venue_id), "hours")
        return await self.set(key, hours, expire)

    async def get_venue_settings(self, venue_id: UUID, category: str = None) -> Optional[dict]:
        """Get cached venue settings."""
        key = self._make_key("venue", str(venue_id), "settings", category or "all")
        return await self.get(key)

    async def set_venue_settings(self, venue_id: UUID, settings_data: dict, category: str = None, expire: int = 300) -> bool:
        """Cache venue settings."""
        key = self._make_key("venue", str(venue_id), "settings", category or "all")
        return await self.set(key, settings_data, expire)


# Global cache manager instance
cache_manager = CacheManager()


def cached(
    prefix: str,
    expire: int = 300,
    key_builder: Callable[..., str] = None,
):
    """
    Decorator for caching function results.

    Usage:
        @cached("venue_list", expire=60)
        async def get_venues(filters, pagination):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = cache_manager._make_key(prefix, *args[1:], **kwargs)

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, expire)
            logger.debug("cache_miss", key=cache_key)

            return result
        return wrapper
    return decorator


def invalidate_cache(patterns: list[str]):
    """
    Decorator to invalidate cache after function execution.

    Usage:
        @invalidate_cache(["venue:{venue_id}*"])
        async def update_venue(venue_id, data):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            result = await func(*args, **kwargs)

            # Invalidate cache patterns
            for pattern in patterns:
                # Replace placeholders with actual values from kwargs
                actual_pattern = pattern
                for key, value in kwargs.items():
                    actual_pattern = actual_pattern.replace(f"{{{key}}}", str(value))
                await cache_manager.delete_pattern(actual_pattern)

            return result
        return wrapper
    return decorator
