"""
=============================================================================
FILE: api/v1/bookings.py
PURPOSE: Party booking CRUD and workflow API endpoints
=============================================================================
"""

from datetime import date, time
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.party import (
    PartyBookingCreate,
    PartyBookingUpdate,
    PartyBookingResponse,
    PartyBookingListResponse,
    PartyBookingDetailResponse,
    PartyBookingStatusUpdate,
    BookingAddonCreate,
    BookingAddonResponse,
    PaginationParams,
)
from app.models.party import BookingStatus, BookingType
from app.services.booking_service import BookingService
from app.core.dependencies import get_booking_service, get_current_user

router = APIRouter()


@router.get("", response_model=PartyBookingListResponse)
async def list_bookings(
    venue_id: UUID = Query(..., description="Venue ID to list bookings for"),
    status: Optional[BookingStatus] = Query(default=None),
    booking_type: Optional[BookingType] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    customer_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="party_date"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all party bookings for a venue.

    Supports filtering by status, type, date range, and customer.
    """
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    bookings, total = await booking_service.list_bookings(
        venue_id=venue_id,
        pagination=pagination,
        status=status,
        booking_type=booking_type,
        date_from=date_from,
        date_to=date_to,
        customer_id=customer_id,
    )

    total_pages = (total + page_size - 1) // page_size

    return PartyBookingListResponse(
        bookings=[PartyBookingResponse.model_validate(b) for b in bookings],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=PartyBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_data: PartyBookingCreate,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new party booking.

    Automatically calculates pricing based on package and addons.
    Creates default timeline if enabled.
    """
    try:
        booking = await booking_service.create_booking(booking_data)
        return PartyBookingResponse.model_validate(booking)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/today", response_model=list[PartyBookingDetailResponse])
async def get_today_bookings(
    venue_id: UUID = Query(..., description="Venue ID"),
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get all bookings for today at a venue."""
    bookings = await booking_service.get_today_bookings(venue_id)
    return [PartyBookingDetailResponse.model_validate(b) for b in bookings]


@router.get("/check-availability")
async def check_availability(
    venue_id: UUID = Query(...),
    party_date: date = Query(...),
    start_time: time = Query(...),
    duration_minutes: int = Query(default=120, ge=30),
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Check if a time slot is available for booking."""
    available = await booking_service.check_availability(
        venue_id=venue_id,
        party_date=party_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
    )
    return {"available": available}


@router.get("/reference/{reference}", response_model=PartyBookingDetailResponse)
async def get_booking_by_reference(
    reference: str,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get booking by reference code."""
    booking = await booking_service.get_booking_by_reference(reference)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingDetailResponse.model_validate(booking)


@router.get("/{booking_id}", response_model=PartyBookingDetailResponse)
async def get_booking(
    booking_id: UUID,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get booking by ID with all related data."""
    booking = await booking_service.get_booking(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingDetailResponse.model_validate(booking)


@router.put("/{booking_id}", response_model=PartyBookingResponse)
async def update_booking(
    booking_id: UUID,
    update_data: PartyBookingUpdate,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update booking information."""
    booking = await booking_service.update_booking(booking_id, update_data)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingResponse.model_validate(booking)


@router.patch("/{booking_id}/status", response_model=PartyBookingResponse)
async def update_booking_status(
    booking_id: UUID,
    status_update: PartyBookingStatusUpdate,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update booking status."""
    booking = await booking_service.update_booking_status(booking_id, status_update)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingResponse.model_validate(booking)


@router.post("/{booking_id}/check-in", response_model=PartyBookingResponse)
async def check_in_booking(
    booking_id: UUID,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Check in a party booking."""
    booking = await booking_service.check_in_booking(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingResponse.model_validate(booking)


@router.post("/{booking_id}/complete", response_model=PartyBookingResponse)
async def complete_booking(
    booking_id: UUID,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Complete a party booking."""
    booking = await booking_service.complete_booking(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingResponse.model_validate(booking)


@router.post("/{booking_id}/cancel", response_model=PartyBookingResponse)
async def cancel_booking(
    booking_id: UUID,
    cancellation_reason: Optional[str] = Query(default=None),
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Cancel a party booking."""
    booking = await booking_service.cancel_booking(booking_id, cancellation_reason)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    return PartyBookingResponse.model_validate(booking)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(
    booking_id: UUID,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Soft delete a booking."""
    deleted = await booking_service.delete_booking(booking_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )


# Booking Addons
@router.post("/{booking_id}/addons", response_model=BookingAddonResponse, status_code=status.HTTP_201_CREATED)
async def add_booking_addon(
    booking_id: UUID,
    addon_data: BookingAddonCreate,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Add an addon to a booking."""
    addon_data.addon_id  # Ensure addon_id is in data
    result = await booking_service.add_booking_addon(booking_id, addon_data)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking or addon not found",
        )
    return BookingAddonResponse.model_validate(result)


@router.delete("/{booking_id}/addons/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_booking_addon(
    booking_id: UUID,
    addon_id: UUID,
    booking_service: BookingService = Depends(get_booking_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Remove an addon from a booking."""
    deleted = await booking_service.remove_booking_addon(booking_id, addon_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking addon not found",
        )
