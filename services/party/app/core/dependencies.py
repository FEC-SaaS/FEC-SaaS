"""
=============================================================================
FILE: core/dependencies.py
PURPOSE: FastAPI dependency injection
=============================================================================
"""

from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.core.security import verify_token
from app.services.package_service import PackageService
from app.services.addon_service import AddonService
from app.services.booking_service import BookingService
from app.services.corporate_event_service import CorporateEventService
from app.services.timeline_service import TimelineService
from app.services.analytics_service import AnalyticsService


# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    Get current user from JWT token.

    Returns:
        User payload from token
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = verify_token(credentials.credentials)
    return payload


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        return verify_token(credentials.credentials)
    except HTTPException:
        return None


# Service dependencies
async def get_package_service(
    db: AsyncSession = Depends(get_db),
) -> PackageService:
    """Get PackageService instance."""
    return PackageService(db)


async def get_addon_service(
    db: AsyncSession = Depends(get_db),
) -> AddonService:
    """Get AddonService instance."""
    return AddonService(db)


async def get_booking_service(
    db: AsyncSession = Depends(get_db),
) -> BookingService:
    """Get BookingService instance."""
    return BookingService(db)


async def get_corporate_event_service(
    db: AsyncSession = Depends(get_db),
) -> CorporateEventService:
    """Get CorporateEventService instance."""
    return CorporateEventService(db)


async def get_timeline_service(
    db: AsyncSession = Depends(get_db),
) -> TimelineService:
    """Get TimelineService instance."""
    return TimelineService(db)


async def get_analytics_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsService:
    """Get AnalyticsService instance."""
    return AnalyticsService(db)
