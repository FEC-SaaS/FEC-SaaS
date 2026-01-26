"""
=============================================================================
FILE: api/v1/timeline.py
PURPOSE: Party timeline and host assignment API endpoints
=============================================================================
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.party import (
    PartyTimelineCreate,
    PartyTimelineUpdate,
    PartyTimelineResponse,
    TimelineItemComplete,
    HostAssignmentCreate,
    HostAssignmentUpdate,
    HostAssignmentResponse,
)
from app.services.timeline_service import TimelineService
from app.core.dependencies import get_timeline_service, get_current_user

router = APIRouter()


# =============================================================================
# Timeline Endpoints
# =============================================================================


@router.get("/bookings/{booking_id}/timeline", response_model=list[PartyTimelineResponse])
async def get_booking_timeline(
    booking_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get all timeline items for a booking in order."""
    items = await timeline_service.get_booking_timeline(booking_id)
    return [PartyTimelineResponse.model_validate(i) for i in items]


@router.get("/bookings/{booking_id}/timeline/progress")
async def get_timeline_progress(
    booking_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get timeline completion progress for a booking."""
    return await timeline_service.get_timeline_progress(booking_id)


@router.post("/bookings/{booking_id}/timeline", response_model=PartyTimelineResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline_item(
    booking_id: UUID,
    item_data: PartyTimelineCreate,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new timeline item for a booking."""
    item_data.booking_id = booking_id
    item = await timeline_service.create_timeline_item(item_data)
    return PartyTimelineResponse.model_validate(item)


@router.put("/timeline/{item_id}", response_model=PartyTimelineResponse)
async def update_timeline_item(
    item_id: UUID,
    update_data: PartyTimelineUpdate,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update a timeline item."""
    item = await timeline_service.update_timeline_item(item_id, update_data)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline item not found",
        )
    return PartyTimelineResponse.model_validate(item)


@router.post("/timeline/{item_id}/start", response_model=PartyTimelineResponse)
async def start_timeline_item(
    item_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Mark a timeline item as in progress."""
    item = await timeline_service.start_timeline_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline item not found",
        )
    return PartyTimelineResponse.model_validate(item)


@router.post("/timeline/{item_id}/complete", response_model=PartyTimelineResponse)
async def complete_timeline_item(
    item_id: UUID,
    completion_data: TimelineItemComplete,
    timeline_service: TimelineService = Depends(get_timeline_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Mark a timeline item as completed."""
    user_id = UUID(current_user.get("sub", current_user.get("user_id")))
    item = await timeline_service.complete_timeline_item(item_id, completion_data, user_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline item not found",
        )
    return PartyTimelineResponse.model_validate(item)


@router.post("/timeline/{item_id}/skip", response_model=PartyTimelineResponse)
async def skip_timeline_item(
    item_id: UUID,
    reason: Optional[str] = Query(default=None),
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Skip a timeline item."""
    item = await timeline_service.skip_timeline_item(item_id, reason)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline item not found",
        )
    return PartyTimelineResponse.model_validate(item)


@router.delete("/timeline/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline_item(
    item_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a timeline item."""
    deleted = await timeline_service.delete_timeline_item(item_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline item not found",
        )


# =============================================================================
# Host Assignment Endpoints
# =============================================================================


@router.get("/bookings/{booking_id}/staff", response_model=list[HostAssignmentResponse])
async def get_booking_staff(
    booking_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get all host assignments for a booking."""
    assignments = await timeline_service.get_booking_assignments(booking_id)
    return [HostAssignmentResponse.model_validate(a) for a in assignments]


@router.post("/bookings/{booking_id}/staff", response_model=HostAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_host(
    booking_id: UUID,
    assignment_data: HostAssignmentCreate,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Assign a staff member to a party."""
    assignment_data.booking_id = booking_id
    assignment = await timeline_service.create_host_assignment(assignment_data)
    return HostAssignmentResponse.model_validate(assignment)


@router.get("/staff/{staff_id}/assignments", response_model=list[HostAssignmentResponse])
async def get_staff_assignments(
    staff_id: UUID,
    party_date: Optional[datetime] = Query(default=None),
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get all assignments for a staff member."""
    assignments = await timeline_service.get_staff_assignments(staff_id, party_date)
    return [HostAssignmentResponse.model_validate(a) for a in assignments]


@router.put("/staff/assignment/{assignment_id}", response_model=HostAssignmentResponse)
async def update_assignment(
    assignment_id: UUID,
    update_data: HostAssignmentUpdate,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update a host assignment."""
    assignment = await timeline_service.update_host_assignment(assignment_id, update_data)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    return HostAssignmentResponse.model_validate(assignment)


@router.post("/staff/assignment/{assignment_id}/confirm", response_model=HostAssignmentResponse)
async def confirm_assignment(
    assignment_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Confirm a host assignment."""
    assignment = await timeline_service.confirm_assignment(assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    return HostAssignmentResponse.model_validate(assignment)


@router.post("/staff/assignment/{assignment_id}/check-in", response_model=HostAssignmentResponse)
async def check_in_host(
    assignment_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Check in a host for their assignment."""
    assignment = await timeline_service.check_in_host(assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    return HostAssignmentResponse.model_validate(assignment)


@router.delete("/staff/assignment/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: UUID,
    timeline_service: TimelineService = Depends(get_timeline_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Remove a host assignment."""
    deleted = await timeline_service.delete_host_assignment(assignment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
