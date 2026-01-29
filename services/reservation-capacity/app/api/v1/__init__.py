"""Reservation & Capacity API v1 router."""

from fastapi import APIRouter

from app.api.v1.reservations import router as reservations_router
from app.api.v1.availability import router as availability_router
from app.api.v1.capacity import router as capacity_router
from app.api.v1.waitlist import router as waitlist_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.no_shows import router as no_shows_router
from app.api.v1.overbooking import router as overbooking_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.recurring import router as recurring_router
from app.api.v1.group_bookings import router as group_bookings_router
from app.api.v1.deposits import router as deposits_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(reservations_router, tags=["Reservations"])
api_router.include_router(availability_router, tags=["Availability"])
api_router.include_router(capacity_router, tags=["Capacity"])
api_router.include_router(waitlist_router, tags=["Waitlist"])
api_router.include_router(reminders_router, tags=["Reminders"])
api_router.include_router(no_shows_router, tags=["No-Shows"])
api_router.include_router(overbooking_router, tags=["Overbooking"])
api_router.include_router(analytics_router, tags=["Analytics"])
api_router.include_router(recurring_router, tags=["Recurring Reservations"])
api_router.include_router(group_bookings_router, tags=["Group Bookings"])
api_router.include_router(deposits_router, tags=["Deposits"])
