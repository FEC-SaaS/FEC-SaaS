"""
=============================================================================
FILE: core/security.py
PURPOSE: JWT token verification and security utilities
=============================================================================
"""

from typing import Dict, Any

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token and return payload.

    Args:
        token: JWT token string

    Returns:
        Token payload dictionary

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_id_from_token(token: str) -> str:
    """Extract user ID from token."""
    payload = verify_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID",
        )
    return user_id


def get_venue_ids_from_token(token: str) -> list:
    """Extract venue IDs from token (for multi-venue access)."""
    payload = verify_token(token)
    return payload.get("venue_ids", [])
