"""
=============================================================================
FILE: core/security.py
PURPOSE: JWT token verification and security utilities
=============================================================================
"""

from typing import Optional, Dict, Any
from datetime import datetime

from jose import jwt, JWTError
from fastapi import HTTPException, status
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )

        return payload

    except JWTError as e:
        logger.warning("token_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from token."""
    try:
        payload = verify_token(token)
        return payload.get("sub")
    except HTTPException:
        return None
