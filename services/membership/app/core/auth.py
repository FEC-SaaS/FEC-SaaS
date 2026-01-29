"""
=============================================================================
FILE: core/auth.py
PURPOSE: Authentication and authorization utilities
=============================================================================
"""

from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Decode and validate JWT token from Authorization header.
    Returns the decoded user payload.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Validate required fields
        user_id = payload.get("sub")
        customer_id = payload.get("customer_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "user_id": UUID(user_id) if user_id else None,
            "customer_id": UUID(customer_id) if customer_id else None,
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "venue_access": payload.get("venue_access", {}),
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_venue_access(
    current_user: Dict[str, Any],
    venue_id: UUID,
    required_role: str = "staff",
) -> None:
    """
    Verify user has access to a specific venue.

    Roles hierarchy:
    - admin: Full access
    - manager: Can manage venue settings and staff
    - staff: Can perform operations
    """
    # System admins have access to all venues
    if "admin" in current_user.get("roles", []):
        return

    venue_access = current_user.get("venue_access", {})
    venue_key = str(venue_id)

    if venue_key not in venue_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this venue",
        )

    user_role = venue_access[venue_key]
    role_hierarchy = {"admin": 3, "manager": 2, "staff": 1}

    required_level = role_hierarchy.get(required_role, 1)
    user_level = role_hierarchy.get(user_role, 0)

    if user_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires {required_role} role or higher",
        )


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[Dict[str, Any]]:
    """
    Get current user if authenticated, otherwise return None.
    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": UUID(payload.get("sub")) if payload.get("sub") else None,
            "customer_id": UUID(payload.get("customer_id")) if payload.get("customer_id") else None,
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "venue_access": payload.get("venue_access", {}),
        }
    except (jwt.InvalidTokenError, Exception):
        return None
