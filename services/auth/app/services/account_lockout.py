"""Account lockout service to prevent brute-force attacks."""
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.config import get_settings
from app.core.redis import get_redis_client

settings = get_settings()

# Redis key prefixes
FAILED_ATTEMPTS_PREFIX = "failed_login:"
LOCKOUT_PREFIX = "account_locked:"

# Lockout configuration
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 15 * 60  # 15 minutes
FAILED_ATTEMPT_WINDOW_SECONDS = 5 * 60  # 5 minute window for counting attempts


class AccountLockoutService:
    """Service for managing account lockouts after failed login attempts."""

    @classmethod
    def is_account_locked(cls, identifier: str) -> Tuple[bool, Optional[int]]:
        """Check if an account is locked.

        Args:
            identifier: Email or user ID

        Returns:
            Tuple of (is_locked, seconds_remaining)
        """
        redis_client = get_redis_client()
        if not redis_client:
            # If Redis unavailable, don't lock (fail open for availability)
            return False, None

        try:
            lockout_key = f"{LOCKOUT_PREFIX}{identifier.lower()}"
            ttl = redis_client.ttl(lockout_key)

            if ttl > 0:
                return True, ttl
            return False, None
        except Exception:
            return False, None

    @classmethod
    def record_failed_attempt(cls, identifier: str) -> Tuple[int, bool]:
        """Record a failed login attempt.

        Args:
            identifier: Email or user ID

        Returns:
            Tuple of (attempt_count, is_now_locked)
        """
        redis_client = get_redis_client()
        if not redis_client:
            return 0, False

        try:
            identifier = identifier.lower()
            attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{identifier}"

            # Increment failed attempts
            attempts = redis_client.incr(attempts_key)

            # Set expiry on first attempt
            if attempts == 1:
                redis_client.expire(attempts_key, FAILED_ATTEMPT_WINDOW_SECONDS)

            # Check if we need to lock the account
            if attempts >= MAX_FAILED_ATTEMPTS:
                lockout_key = f"{LOCKOUT_PREFIX}{identifier}"
                redis_client.setex(lockout_key, LOCKOUT_DURATION_SECONDS, "1")
                # Clear the failed attempts counter
                redis_client.delete(attempts_key)
                return attempts, True

            return attempts, False
        except Exception:
            return 0, False

    @classmethod
    def clear_failed_attempts(cls, identifier: str) -> bool:
        """Clear failed attempts after successful login.

        Args:
            identifier: Email or user ID

        Returns:
            True if cleared successfully
        """
        redis_client = get_redis_client()
        if not redis_client:
            return False

        try:
            identifier = identifier.lower()
            attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{identifier}"
            redis_client.delete(attempts_key)
            return True
        except Exception:
            return False

    @classmethod
    def get_remaining_attempts(cls, identifier: str) -> int:
        """Get remaining login attempts before lockout.

        Args:
            identifier: Email or user ID

        Returns:
            Number of remaining attempts
        """
        redis_client = get_redis_client()
        if not redis_client:
            return MAX_FAILED_ATTEMPTS

        try:
            identifier = identifier.lower()
            attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{identifier}"
            current = redis_client.get(attempts_key)

            if current:
                return max(0, MAX_FAILED_ATTEMPTS - int(current))
            return MAX_FAILED_ATTEMPTS
        except Exception:
            return MAX_FAILED_ATTEMPTS

    @classmethod
    def unlock_account(cls, identifier: str) -> bool:
        """Manually unlock an account (admin action).

        Args:
            identifier: Email or user ID

        Returns:
            True if unlocked successfully
        """
        redis_client = get_redis_client()
        if not redis_client:
            return False

        try:
            identifier = identifier.lower()
            lockout_key = f"{LOCKOUT_PREFIX}{identifier}"
            attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{identifier}"
            redis_client.delete(lockout_key, attempts_key)
            return True
        except Exception:
            return False
