"""
=============================================================================
FILE: api/v1/performance.py
PURPOSE: Venue performance tracking and benchmarking endpoints
=============================================================================
"""

from datetime import date
from typing import List, Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.venue import (
    VenuePerformanceCreate,
    VenuePerformanceResponse,
    PerformanceComparison,
)
from app.services.performance_service import PerformanceService
from app.core.dependencies import get_performance_service, get_current_user

router = APIRouter()


@router.get("/{venue_id}/performance", response_model=List[VenuePerformanceResponse])
async def get_performance_history(
    venue_id: UUID,
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    metric_type: str = Query(default=None),
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get performance history for a venue.

    Optionally filter by date range and metric type.
    """
    return await performance_service.get_performance_history(
        venue_id,
        start_date=start_date,
        end_date=end_date,
        metric_type=metric_type,
    )


@router.get("/{venue_id}/performance/latest", response_model=Optional[VenuePerformanceResponse])
async def get_latest_performance(
    venue_id: UUID,
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get the latest performance snapshot for a venue."""
    return await performance_service.get_latest_performance(venue_id)


@router.post(
    "/{venue_id}/performance",
    response_model=VenuePerformanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_performance(
    venue_id: UUID,
    performance_data: VenuePerformanceCreate,
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Record a new performance snapshot for a venue."""
    return await performance_service.record_performance(venue_id, performance_data)


@router.get("/{venue_id}/performance/summary")
async def get_performance_summary(
    venue_id: UUID,
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get aggregated performance summary for a venue.

    Returns averages, trends, and key metrics over the specified period.
    """
    return await performance_service.get_performance_summary(
        venue_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{venue_id}/performance/compare", response_model=PerformanceComparison)
async def compare_performance(
    venue_id: UUID,
    compare_to: List[UUID] = Query(default=[]),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Compare venue performance against other venues or franchise average.

    Useful for benchmarking within a franchise.
    """
    return await performance_service.compare_venues(
        venue_id,
        compare_to_ids=compare_to,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/franchise/{franchise_id}/performance/leaderboard")
async def get_franchise_leaderboard(
    franchise_id: UUID,
    metric: str = Query(default="revenue"),
    period: str = Query(default="month", pattern="^(day|week|month|quarter|year)$"),
    limit: int = Query(default=10, ge=1, le=50),
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get franchise venue performance leaderboard.

    Ranks venues by specified metric over the given period.
    """
    return await performance_service.get_franchise_leaderboard(
        franchise_id,
        metric=metric,
        period=period,
        limit=limit,
    )


@router.get("/{venue_id}/performance/trends")
async def get_performance_trends(
    venue_id: UUID,
    metrics: List[str] = Query(default=["revenue", "bookings", "satisfaction"]),
    period: str = Query(default="month", pattern="^(day|week|month|quarter|year)$"),
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get performance trend analysis for specified metrics.

    Returns trend direction, percentage change, and projections.
    """
    return await performance_service.analyze_trends(
        venue_id,
        metrics=metrics,
        period=period,
    )


@router.delete("/{venue_id}/performance/{performance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance_record(
    venue_id: UUID,
    performance_id: UUID,
    performance_service: PerformanceService = Depends(get_performance_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a specific performance record."""
    deleted = await performance_service.delete_performance(venue_id, performance_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Performance record not found",
        )
