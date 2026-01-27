"""
=============================================================================
FILE: core/dependencies.py
PURPOSE: FastAPI dependency injection functions
=============================================================================
"""

from typing import AsyncGenerator, Dict, Any, Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.security import verify_token

logger = structlog.get_logger()
security = HTTPBearer()


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency.

    Yields an async database session from the app state.
    """
    async_session = request.app.state.async_session
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        User data from token payload

    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub") or payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "venue_id": payload.get("venue_id"),
        "permissions": payload.get("permissions", []),
    }


async def get_optional_user(
    request: Request,
) -> Optional[Dict[str, Any]]:
    """
    Get current user if authenticated, None otherwise.

    Used for endpoints that work with or without authentication.
    """
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    payload = verify_token(token)

    if payload is None:
        return None

    return {
        "user_id": payload.get("sub") or payload.get("user_id"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "venue_id": payload.get("venue_id"),
    }


def require_permissions(*permissions: str):
    """
    Dependency factory for permission checking.

    Args:
        permissions: Required permissions

    Returns:
        Dependency function
    """
    async def check_permissions(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        user_permissions = current_user.get("permissions", [])

        # Admin has all permissions
        if current_user.get("role") == "admin":
            return current_user

        for permission in permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission} required",
                )

        return current_user

    return check_permissions
