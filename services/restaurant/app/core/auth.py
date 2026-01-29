"""JWT authentication and authorization."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Extract and validate JWT token."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return {
            "user_id": UUID(user_id),
            "email": payload.get("email"),
            "role": payload.get("role", "user"),
            "venue_ids": payload.get("venue_ids", []),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def require_venue_access(
    current_user: dict,
    venue_id: UUID,
    required_role: Optional[str] = None,
) -> None:
    """Verify user has access to the specified venue."""
    if current_user.get("role") == "superadmin":
        return

    venue_ids = current_user.get("venue_ids", [])
    if str(venue_id) not in [str(v) for v in venue_ids]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this venue",
        )

    if required_role and current_user.get("role") not in [required_role, "admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {required_role} role",
        )
