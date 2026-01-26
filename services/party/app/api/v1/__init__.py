"""
API v1 routes for Party Service.
"""

from fastapi import APIRouter

from app.api.v1 import packages, addons, bookings, corporate, timeline, analytics

router = APIRouter(prefix="/api/v1/parties")

# Include all routers
router.include_router(packages.router, prefix="/packages", tags=["Packages"])
router.include_router(addons.router, prefix="/addons", tags=["Addons"])
router.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
router.include_router(corporate.router, prefix="/corporate", tags=["Corporate Events"])
router.include_router(timeline.router, tags=["Timeline & Staff"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
