"""
=============================================================================
FILE: deps.py
PURPOSE: FastAPI dependency injection functions for API endpoints
=============================================================================

This module provides reusable dependencies for FastAPI endpoints, including:
- Database session management
- User authentication/authorization
- Request context extraction

WHAT IT DOES:
- Provides database sessions with automatic cleanup
- Extracts and validates current user from JWT tokens
- Checks token blacklist status
- Provides common request context (IP, user agent)

DEPENDENCIES PROVIDED:
- get_db: Database session
- get_current_user: Authenticated user from JWT
- get_current_active_user: Active (non-disabled) user
- get_optional_user: User if authenticated, None otherwise

USAGE:
    from app.api.deps import get_db, get_current_user

    @router.get("/protected")
    async def protected_endpoint(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        ...

=============================================================================
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_token
from app.db.session import get_db as _get_db
from app.models.user import User
from app.services.token_blacklist import TokenBlacklistService

settings = get_settings()

# OAuth2 password bearer for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Optional OAuth2 scheme (doesn't raise error if missing)
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_db():
    """
    Database session dependency.

    Yields a SQLAlchemy session and ensures cleanup after request.
    Uses the session factory from db.session module.
    """
    yield from _get_db()


def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.

    This dependency:
    1. Extracts JWT from Authorization header
    2. Checks if token is blacklisted
    3. Verifies token signature and expiration
    4. Checks if token was issued before security invalidation
    5. Loads and returns the user from database

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found

    Returns:
        User: The authenticated user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check if token is blacklisted
    if TokenBlacklistService.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    payload = verify_token(token, expected_type="access")
    if not payload:
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # Check if token was issued before a security invalidation event
    token_iat = payload.get("iat", 0)
    if TokenBlacklistService.is_token_issued_before_invalidation(user_id, token_iat):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they are active (not disabled).

    Raises:
        HTTPException 403: If user account is disabled

    Returns:
        User: The active authenticated user
    """
    if hasattr(current_user, 'is_active') and not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return current_user


def get_optional_user(
    request: Request,
    token: Annotated[Optional[str], Depends(oauth2_scheme_optional)],
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optionally get the current user if authenticated.

    Unlike get_current_user, this doesn't raise an error if no token
    is provided. Useful for endpoints that work differently for
    authenticated vs anonymous users.

    Returns:
        User: The authenticated user, or None if not authenticated
    """
    if not token:
        return None

    try:
        return get_current_user(request, token, db)
    except HTTPException:
        return None


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.

    Checks X-Forwarded-For header for proxied requests,
    falls back to direct client IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent string from request headers."""
    return request.headers.get("User-Agent", "unknown")


# =============================================================================
# END OF FILE
# =============================================================================
