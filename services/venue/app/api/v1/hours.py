"""
=============================================================================
FILE: api/v1/hours.py
PURPOSE: Venue hours management endpoints
=============================================================================
"""

from datetime import date, time
from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.venue import (
    VenueHoursCreate,
    VenueHoursUpdate,
    VenueHoursResponse,
    VenueSpecialHoursCreate,
    VenueSpecialHoursResponse,
)
from app.services.hours_service import HoursService
from app.core.dependencies import get_hours_service, get_current_user

router = APIRouter()


@router.get("/{venue_id}/hours", response_model=List[VenueHoursResponse])
async def get_venue_hours(
    venue_id: UUID,
    hours_service: HoursService = Depends(get_hours_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get regular operating hours for a venue."""
    return await hours_service.get_hours(venue_id)


@router.put("/{venue_id}/hours", response_model=List[VenueHoursResponse])
async def set_venue_hours(
    venue_id: UUID,
    hours_list: List[VenueHoursCreate],
    hours_service: HoursService = Depends(get_hours_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Set regular operating hours for a venue.

    Replaces all existing hours with the provided list.
    """
    return await hours_service.set_hours(venue_id, hours_list)


@router.patch("/{venue_id}/hours/{day_of_week}", response_model=VenueHoursResponse)
async def update_day_hours(
    venue_id: UUID,
    day_of_week: int,
    update_data: VenueHoursUpdate,
    hours_service: HoursService = Depends(get_hours_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update hours for a specific day."""
    if day_of_week < 0 or day_of_week > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week must be between 0 (Sunday) and 6 (Saturday)",
        )
    hours = await hours_service.update_day_hours(venue_id, day_of_week, update_data)
    return hours


@router.get("/{venue_id}/is-open")
async def check_is_open(
    venue_id: UUID,
    check_date: date = Query(default=None),
    check_time: time = Query(default=None),
    hours_service: HoursService = Depends(get_hours_service),
):
    """
    Check if venue is open at a given date/time.

    Defaults to current date/time if not specified.
    """
    is_open = await hours_service.is_open(venue_id, check_date, check_time)
    return {"venue_id": venue_id, "is_open": is_open}


# Special hours endpoints
@router.get("/{venue_id}/hours/special", response_model=List[VenueSpecialHoursResponse])
async def get_special_hours(
    venue_id: UUID,
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    hours_service: HoursService = Depends(get_hours_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get special hours for a venue within date range."""
    return await hours_service.get_special_hours(venue_id, start_date, end_date)


@router.post(
    "/{venue_id}/hours/special",
    response_model=VenueSpecialHoursResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_special_hours(
    venue_id: UUID,
    special_data: VenueSpecialHoursCreate,
    hours_service: HoursService = Depends(get_hours_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Create special hours for a date (e.g., holiday hours)."""
    return await hours_service.create_special_hours(venue_id, special_data)


@router.delete("/{venue_id}/hours/special/{special_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_special_hours(
    venue_id: UUID,
    special_id: UUID,
    hours_service: HoursService = Depends(get_hours_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Delete special hours entry."""
    deleted = await hours_service.delete_special_hours(venue_id, special_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special hours not found",
        )
