"""
=============================================================================
FILE: api/v1/analytics.py
PURPOSE: Party analytics API endpoints
=============================================================================
"""

from datetime import date, timedelta
from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.schemas.party import (
    PartyRevenueStats,
    PartyPerformanceMetrics,
    UpsellConversionStats,
)
from app.services.analytics_service import AnalyticsService
from app.core.dependencies import get_analytics_service, get_current_user

router = APIRouter()


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_dashboard_summary(
    venue_id: UUID = Query(..., description="Venue ID"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get quick dashboard summary for today and this week.

    Returns counts and totals for immediate operational awareness.
    """
    return await analytics_service.get_dashboard_summary(venue_id)


@router.get("/revenue", response_model=PartyRevenueStats)
async def get_revenue_stats(
    venue_id: UUID = Query(..., description="Venue ID"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    include_comparison: bool = Query(default=True),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get party revenue statistics for a date range.

    If dates not specified, defaults to current month.
    Includes comparison to previous period if requested.
    """
    if not start_date:
        today = date.today()
        start_date = today.replace(day=1)
    if not end_date:
        end_date = date.today()

    return await analytics_service.get_revenue_stats(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
        include_comparison=include_comparison,
    )


@router.get("/performance", response_model=PartyPerformanceMetrics)
async def get_performance_metrics(
    venue_id: UUID = Query(..., description="Venue ID"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get party performance metrics for a date range.

    Returns completion rates, average party size, on-time performance, etc.
    """
    if not start_date:
        today = date.today()
        start_date = today.replace(day=1)
    if not end_date:
        end_date = date.today()

    return await analytics_service.get_performance_metrics(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/upsells", response_model=UpsellConversionStats)
async def get_upsell_stats(
    venue_id: UUID = Query(..., description="Venue ID"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get upsell conversion statistics for a date range.

    Returns addon attachment rates and AI upsell performance.
    """
    if not start_date:
        today = date.today()
        start_date = today.replace(day=1)
    if not end_date:
        end_date = date.today()

    return await analytics_service.get_upsell_stats(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
    )
