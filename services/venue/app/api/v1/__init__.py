"""
API v1 routes.
"""

from fastapi import APIRouter

from app.api.v1 import venues, hours, settings, features, ai_config, performance, onboarding

router = APIRouter(prefix="/api/v1")

# Include all routers
router.include_router(venues.router, prefix="/venues", tags=["Venues"])
router.include_router(hours.router, prefix="/venues", tags=["Hours"])
router.include_router(settings.router, prefix="/venues", tags=["Settings"])
router.include_router(features.router, prefix="/venues", tags=["Features"])
router.include_router(ai_config.router, prefix="/venues", tags=["AI Config"])
router.include_router(performance.router, prefix="/venues", tags=["Performance"])
router.include_router(onboarding.router, prefix="/venues", tags=["Onboarding"])
