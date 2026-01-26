"""
=============================================================================
FILE: api/v1/corporate.py
PURPOSE: Corporate event API endpoints
=============================================================================
"""

from datetime import date, datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.party import (
    CorporateEventCreate,
    CorporateEventUpdate,
    CorporateEventResponse,
    CorporateEventListResponse,
    CorporateEventStatusUpdate,
    PaginationParams,
)
from app.models.party import CorporateEventType, CorporateEventStatus
from app.services.corporate_event_service import CorporateEventService
from app.core.dependencies import get_corporate_event_service, get_current_user

router = APIRouter()


@router.get("", response_model=CorporateEventListResponse)
async def list_events(
    venue_id: UUID = Query(..., description="Venue ID to list events for"),
    status: Optional[CorporateEventStatus] = Query(default=None),
    event_type: Optional[CorporateEventType] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    min_lead_score: Optional[int] = Query(default=None, ge=0, le=100),
    assigned_rep_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all corporate events for a venue.

    Supports filtering by status, type, date range, lead score, and assigned rep.
    """
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    events, total = await event_service.list_events(
        venue_id=venue_id,
        pagination=pagination,
        status=status,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
        min_lead_score=min_lead_score,
        assigned_rep_id=assigned_rep_id,
    )

    total_pages = (total + page_size - 1) // page_size

    return CorporateEventListResponse(
        events=[CorporateEventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=CorporateEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: CorporateEventCreate,
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new corporate event inquiry.

    Automatically calculates AI-based lead score.
    """
    event = await event_service.create_event(event_data)
    return CorporateEventResponse.model_validate(event)


@router.get("/high-priority", response_model=list[CorporateEventResponse])
async def get_high_priority_leads(
    venue_id: UUID = Query(..., description="Venue ID"),
    limit: int = Query(default=10, ge=1, le=50),
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get high priority leads sorted by lead score."""
    events = await event_service.get_high_priority_leads(venue_id, limit)
    return [CorporateEventResponse.model_validate(e) for e in events]


@router.get("/follow-ups-due", response_model=list[CorporateEventResponse])
async def get_follow_ups_due(
    venue_id: UUID = Query(..., description="Venue ID"),
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get events with follow-ups due."""
    events = await event_service.get_follow_ups_due(venue_id)
    return [CorporateEventResponse.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=CorporateEventResponse)
async def get_event(
    event_id: UUID,
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get event by ID."""
    event = await event_service.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return CorporateEventResponse.model_validate(event)


@router.put("/{event_id}", response_model=CorporateEventResponse)
async def update_event(
    event_id: UUID,
    update_data: CorporateEventUpdate,
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update event information."""
    event = await event_service.update_event(event_id, update_data)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return CorporateEventResponse.model_validate(event)


@router.patch("/{event_id}/status", response_model=CorporateEventResponse)
async def update_event_status(
    event_id: UUID,
    status_update: CorporateEventStatusUpdate,
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update event status."""
    event = await event_service.update_event_status(event_id, status_update)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return CorporateEventResponse.model_validate(event)


@router.post("/{event_id}/assign", response_model=CorporateEventResponse)
async def assign_sales_rep(
    event_id: UUID,
    rep_id: UUID = Query(..., description="Sales rep user ID"),
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Assign a sales rep to the event."""
    event = await event_service.assign_sales_rep(event_id, rep_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return CorporateEventResponse.model_validate(event)


@router.post("/{event_id}/follow-up", response_model=CorporateEventResponse)
async def set_follow_up(
    event_id: UUID,
    follow_up_date: datetime = Query(...),
    notes: Optional[str] = Query(default=None),
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Set next follow-up date and notes."""
    event = await event_service.set_follow_up(event_id, follow_up_date, notes)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return CorporateEventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    event_service: CorporateEventService = Depends(get_corporate_event_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Soft delete an event."""
    deleted = await event_service.delete_event(event_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
