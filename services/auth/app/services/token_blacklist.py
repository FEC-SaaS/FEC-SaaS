"""Token blacklist service using Redis for JWT invalidation."""
from datetime import datetime, timezone
from typing import Optional

from jose import jwt, JWTError

from app.core.config import get_settings
from app.core.redis import get_redis_client

settings = get_settings()

# Redis key prefixes
BLACKLIST_PREFIX = "token_blacklist:"
REFRESH_TOKEN_PREFIX = "refresh_token:"


class TokenBlacklistService:
    """Service for managing token blacklisting with Redis."""

    @staticmethod
    def _get_token_jti(token: str) -> Optional[str]:
        """Extract JTI (JWT ID) from token, or use token hash as fallback."""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False}  # Allow expired tokens to be blacklisted
            )
            # Use 'jti' if present, otherwise hash the subject + exp
            jti = payload.get("jti")
            if jti:
                return jti
            # Fallback: create unique identifier from sub + exp
            sub = payload.get("sub", "")
            exp = payload.get("exp", 0)
            return f"{sub}:{exp}"
        except JWTError:
            return None

    @staticmethod
    def _get_token_expiry(token: str) -> Optional[int]:
        """Get token expiry timestamp."""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False}
            )
            return payload.get("exp")
        except JWTError:
            return None

    @classmethod
    def blacklist_token(cls, token: str) -> bool:
        """Add a token to the blacklist.

        Token will be stored until its natural expiry time.
        Returns True if successfully blacklisted, False otherwise.
        """
        redis_client = get_redis_client()
        if not redis_client:
            # Fallback: log warning, but don't fail the operation
            return False

        token_id = cls._get_token_jti(token)
        if not token_id:
            return False

        # Calculate TTL based on token expiry
        exp = cls._get_token_expiry(token)
        if exp:
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = max(exp - now, 1)  # At least 1 second
        else:
            # Default TTL: 30 days (for refresh tokens)
            ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

        try:
            redis_client.setex(f"{BLACKLIST_PREFIX}{token_id}", ttl, "1")
            return True
        except Exception:
            return False

    @classmethod
    def is_blacklisted(cls, token: str) -> bool:
        """Check if a token is blacklisted."""
        redis_client = get_redis_client()
        if not redis_client:
            # If Redis is unavailable, assume not blacklisted
            # (fail open for availability, but log warning)
            return False

        token_id = cls._get_token_jti(token)
        if not token_id:
            return False

        try:
            return redis_client.exists(f"{BLACKLIST_PREFIX}{token_id}") > 0
        except Exception:
            return False

    @classmethod
    def store_refresh_token(cls, user_id: str, token: str, expires_in: int) -> bool:
        """Store refresh token for tracking and rotation."""
        redis_client = get_redis_client()
        if not redis_client:
            return False

        try:
            # Store the refresh token with user_id as key
            redis_client.setex(
                f"{REFRESH_TOKEN_PREFIX}{user_id}",
                expires_in,
                token
            )
            return True
        except Exception:
            return False

    @classmethod
    def get_stored_refresh_token(cls, user_id: str) -> Optional[str]:
        """Get the current valid refresh token for a user."""
        redis_client = get_redis_client()
        if not redis_client:
            return None

        try:
            return redis_client.get(f"{REFRESH_TOKEN_PREFIX}{user_id}")
        except Exception:
            return None

    @classmethod
    def invalidate_user_refresh_token(cls, user_id: str) -> bool:
        """Invalidate a user's refresh token (for logout)."""
        redis_client = get_redis_client()
        if not redis_client:
            return False

        try:
            redis_client.delete(f"{REFRESH_TOKEN_PREFIX}{user_id}")
            return True
        except Exception:
            return False

    @classmethod
    def blacklist_all_user_tokens(cls, user_id: str) -> bool:
        """Blacklist all tokens for a user (password change, security event)."""
        redis_client = get_redis_client()
        if not redis_client:
            return False

        try:
            # Store a marker that invalidates all tokens issued before now
            now = int(datetime.now(timezone.utc).timestamp())
            # This marker lasts for the max token lifetime (refresh token duration)
            ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            redis_client.setex(f"user_token_invalidation:{user_id}", ttl, str(now))
            return True
        except Exception:
            return False

    @classmethod
    def is_token_issued_before_invalidation(cls, user_id: str, token_iat: int) -> bool:
        """Check if token was issued before user's token invalidation."""
        redis_client = get_redis_client()
        if not redis_client:
            return False

        try:
            invalidation_time = redis_client.get(f"user_token_invalidation:{user_id}")
            if invalidation_time:
                return token_iat < int(invalidation_time)
            return False
        except Exception:
            return False
