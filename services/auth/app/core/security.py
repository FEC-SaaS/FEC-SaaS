"""Security utilities for password hashing and JWT tokens.

Uses bcrypt directly (not passlib) for Python 3.12 compatibility.
Includes JTI (JWT ID) for token tracking and blacklisting.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> Tuple[str, str, int]:
    """Create a JWT access token with JTI for tracking.

    Returns:
        Tuple of (token, jti, expires_in_seconds)
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid.uuid4())

    to_encode: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "access",
    }

    if additional_claims:
        to_encode.update(additional_claims)

    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    expires_in = int(expires_delta.total_seconds())

    return token, jti, expires_in


def create_refresh_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, str, int]:
    """Create a JWT refresh token with JTI for tracking.

    Returns:
        Tuple of (token, jti, expires_in_seconds)
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid.uuid4())

    to_encode: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }

    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    expires_in = int(expires_delta.total_seconds())

    return token, jti, expires_in


def verify_token(token: str, expected_type: str = "access") -> Optional[dict[str, Any]]:
    """Verify a JWT token and return the full payload.

    Args:
        token: The JWT token to verify
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        Token payload dict or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Verify token type
        token_type = payload.get("type", "access")
        if token_type != expected_type:
            return None

        return payload
    except JWTError:
        return None


def get_token_subject(token: str) -> Optional[str]:
    """Extract subject (user ID) from token without full verification.

    Useful for logging/auditing even with expired tokens.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False}
        )
        return str(payload.get("sub"))
    except JWTError:
        return None


def decode_token_unverified(token: str) -> Optional[dict[str, Any]]:
    """Decode token without verification (for blacklisting expired tokens)."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False}
        )
    except JWTError:
        return None


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False
