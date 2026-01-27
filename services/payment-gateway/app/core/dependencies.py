"""
=============================================================================
FILE: core/dependencies.py
PURPOSE: FastAPI dependencies for Payment Gateway Service
=============================================================================
"""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    from app.main import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Validate JWT token and return current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role", "user"),
            "venue_ids": payload.get("venue_ids", []),
        }
    except JWTError:
        raise credentials_exception


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[dict]:
    """Optionally validate JWT token."""
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def verify_venue_access(user: dict, venue_id: UUID) -> bool:
    """Verify user has access to the specified venue."""
    if user.get("role") == "admin":
        return True
    
    venue_ids = user.get("venue_ids", [])
    return str(venue_id) in venue_ids


class VenueAccessChecker:
    """Dependency for checking venue access."""
    
    def __init__(self, require_admin: bool = False):
        self.require_admin = require_admin
    
    def __call__(
        self,
        venue_id: UUID,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if self.require_admin and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        
        if not verify_venue_access(current_user, venue_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this venue",
            )
        
        return current_user
