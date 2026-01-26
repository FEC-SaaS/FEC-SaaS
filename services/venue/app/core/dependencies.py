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
from app.services.venue_service import VenueService
from app.services.hours_service import HoursService
from app.services.settings_service import SettingsService
from app.services.feature_service import FeatureService
from app.services.ai_config_service import AIConfigService
from app.services.performance_service import PerformanceService
from app.services.onboarding_service import OnboardingService


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
async def get_venue_service(
    db: AsyncSession = Depends(get_db),
) -> VenueService:
    """Get VenueService instance."""
    return VenueService(db)


async def get_hours_service(
    db: AsyncSession = Depends(get_db),
) -> HoursService:
    """Get HoursService instance."""
    return HoursService(db)


async def get_settings_service(
    db: AsyncSession = Depends(get_db),
) -> SettingsService:
    """Get SettingsService instance."""
    return SettingsService(db)


async def get_feature_service(
    db: AsyncSession = Depends(get_db),
) -> FeatureService:
    """Get FeatureService instance."""
    return FeatureService(db)


async def get_ai_config_service(
    db: AsyncSession = Depends(get_db),
) -> AIConfigService:
    """Get AIConfigService instance."""
    return AIConfigService(db)


async def get_performance_service(
    db: AsyncSession = Depends(get_db),
) -> PerformanceService:
    """Get PerformanceService instance."""
    return PerformanceService(db)


async def get_onboarding_service(
    db: AsyncSession = Depends(get_db),
) -> OnboardingService:
    """Get OnboardingService instance."""
    return OnboardingService(db)
