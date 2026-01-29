"""Reservation analytics API routes."""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import (
    ChannelAnalyticsResponse,
    NoShowAnalyticsResponse,
    RevenueAnalyticsResponse,
    UtilizationAnalyticsResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get("/reservations/analytics/utilization", response_model=UtilizationAnalyticsResponse)
async def get_utilization_analytics(
    venue_id: UUID = Query(...),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    resource_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(_get_service),
):
    if not period_start:
        period_start = date.today() - timedelta(days=30)
    if not period_end:
        period_end = date.today()
    return await service.get_utilization_analytics(venue_id, period_start, period_end, resource_type)


@router.get("/reservations/analytics/no-shows", response_model=NoShowAnalyticsResponse)
async def get_no_show_analytics(
    venue_id: UUID = Query(...),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(_get_service),
):
    if not period_start:
        period_start = date.today() - timedelta(days=30)
    if not period_end:
        period_end = date.today()
    return await service.get_no_show_analytics(venue_id, period_start, period_end)


@router.get("/reservations/analytics/revenue", response_model=RevenueAnalyticsResponse)
async def get_revenue_analytics(
    venue_id: UUID = Query(...),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(_get_service),
):
    if not period_start:
        period_start = date.today() - timedelta(days=30)
    if not period_end:
        period_end = date.today()
    return await service.get_revenue_analytics(venue_id, period_start, period_end)


@router.get("/reservations/analytics/channels", response_model=ChannelAnalyticsResponse)
async def get_channel_analytics(
    venue_id: UUID = Query(...),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(_get_service),
):
    if not period_start:
        period_start = date.today() - timedelta(days=30)
    if not period_end:
        period_end = date.today()
    return await service.get_channel_analytics(venue_id, period_start, period_end)
