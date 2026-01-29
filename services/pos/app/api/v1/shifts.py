"""
=============================================================================
FILE: api/v1/shifts.py
PURPOSE: API routes for employee shift management
=============================================================================

Provides RESTful endpoints for managing employee shifts in the POS system.
Supports the full shift lifecycle including scheduling, clock-in/clock-out,
cancellation, and querying active or historical shifts.

Endpoints:
    POST   /pos/shifts              - Create a new scheduled shift
    GET    /pos/shifts              - List shifts with filtering
    GET    /pos/shifts/active       - Get currently active shift for employee
    GET    /pos/shifts/{shift_id}   - Get shift details by ID
    PATCH  /pos/shifts/{shift_id}   - Update shift details
    POST   /pos/shifts/{shift_id}/start  - Start shift (clock-in)
    POST   /pos/shifts/{shift_id}/end    - End shift (clock-out)
    POST   /pos/shifts/{shift_id}/cancel - Cancel scheduled shift
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import ShiftStatus
from app.schemas.pos import ShiftCreate, ShiftResponse, ShiftUpdate
from app.services.event_publisher import event_publisher
from app.services.shift_service import ShiftService

router = APIRouter(prefix="/pos/shifts")


def _get_service(db: AsyncSession = Depends(get_db)) -> ShiftService:
    """
    Dependency injection for ShiftService.

    Creates a new ShiftService instance with the current database session
    and event publisher for handling shift-related operations.

    Args:
        db: Async database session from dependency injection.

    Returns:
        Configured ShiftService instance.
    """
    return ShiftService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/shifts - Create a new shift
# ---------------------------------------------------------------------------
@router.post(
    "",
    response_model=ShiftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new scheduled shift",
    responses={
        201: {"description": "Shift created successfully"},
        400: {"description": "Invalid shift data"},
        401: {"description": "Authentication required"},
    },
)
async def create_shift(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue where the shift will take place",
    ),
    data: ShiftCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """
    Create a new scheduled shift for an employee.

    Creates a shift with SCHEDULED status that can later be started when the
    employee clocks in. The shift includes scheduled start and end times, which
    can be compared against actual times for reporting purposes.

    Args:
        venue_id: UUID of the venue where the shift will occur.
        data: ShiftCreate schema containing:
            - employee_id: UUID of the employee assigned to the shift
            - employee_name: Display name of the employee
            - scheduled_start: Planned start datetime
            - scheduled_end: Planned end datetime
            - notes: Optional notes about the shift
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse with the newly created shift details including:
        - Generated shift ID
        - Initial SCHEDULED status
        - All scheduled times and metadata

    Example Request:
        POST /pos/shifts?venue_id=550e8400-e29b-41d4-a716-446655440000
        {
            "employee_id": "123e4567-e89b-12d3-a456-426614174000",
            "employee_name": "John Smith",
            "scheduled_start": "2024-01-15T09:00:00Z",
            "scheduled_end": "2024-01-15T17:00:00Z",
            "notes": "Opening shift"
        }
    """
    shift = await service.create_shift(venue_id, data)
    return ShiftResponse.model_validate(shift)


# ---------------------------------------------------------------------------
# GET /pos/shifts - List shifts with filtering
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[ShiftResponse],
    summary="List shifts for a venue",
    responses={
        200: {"description": "List of shifts matching criteria"},
        401: {"description": "Authentication required"},
    },
)
async def list_shifts(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to list shifts for",
    ),
    employee_id: Optional[UUID] = Query(
        None,
        description="Filter by specific employee UUID",
    ),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by shift status: scheduled, active, completed, cancelled",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Filter shifts starting on or after this date (inclusive)",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Filter shifts starting on or before this date (inclusive)",
    ),
    skip: int = Query(
        0,
        ge=0,
        description="Number of records to skip for pagination",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of records to return (max 200)",
    ),
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> List[ShiftResponse]:
    """
    List shifts for a venue with optional filtering.

    Retrieves shifts matching the specified criteria, ordered by scheduled
    start time (newest first). Supports filtering by employee, status, and
    date range for flexible reporting and scheduling views.

    Args:
        venue_id: UUID of the venue to query shifts for.
        employee_id: Optional employee UUID to filter results.
        status_filter: Optional shift status to filter by. Valid values:
            - "scheduled": Shifts that haven't started yet
            - "active": Currently active (clocked-in) shifts
            - "completed": Finished shifts
            - "cancelled": Cancelled shifts
        date_from: Optional start date filter (inclusive).
        date_to: Optional end date filter (inclusive).
        skip: Pagination offset (default: 0).
        limit: Maximum results to return (default: 50, max: 200).
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        List of ShiftResponse objects matching the criteria.

    Example Request:
        GET /pos/shifts?venue_id=...&status=active&employee_id=...

    Example Response:
        [
            {
                "id": "...",
                "venue_id": "...",
                "employee_id": "...",
                "employee_name": "John Smith",
                "status": "active",
                "scheduled_start": "2024-01-15T09:00:00Z",
                "scheduled_end": "2024-01-15T17:00:00Z",
                "actual_start": "2024-01-15T08:55:00Z",
                "actual_end": null,
                ...
            }
        ]
    """
    # Convert string status to enum if provided
    shift_status = None
    if status_filter:
        try:
            shift_status = ShiftStatus(status_filter)
        except ValueError:
            # Invalid status, will return empty results
            pass

    shifts = await service.list_shifts(
        venue_id=venue_id,
        employee_id=employee_id,
        status=shift_status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [ShiftResponse.model_validate(s) for s in shifts]


# ---------------------------------------------------------------------------
# GET /pos/shifts/active - Get active shift for an employee
# ---------------------------------------------------------------------------
@router.get(
    "/active",
    response_model=Optional[ShiftResponse],
    summary="Get the currently active shift for an employee",
    responses={
        200: {"description": "Active shift found or null if none"},
        401: {"description": "Authentication required"},
    },
)
async def get_active_shift(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue",
    ),
    employee_id: UUID = Query(
        ...,
        description="UUID of the employee to check",
    ),
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> Optional[ShiftResponse]:
    """
    Get the currently active shift for an employee at a venue.

    An employee can only have one active shift at a time. This endpoint
    is useful for checking clock-in status, preventing duplicate clock-ins,
    and retrieving current shift details for display.

    Args:
        venue_id: UUID of the venue to check.
        employee_id: UUID of the employee to look up.
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse if an active shift exists, None otherwise.

    Example Request:
        GET /pos/shifts/active?venue_id=...&employee_id=...

    Example Response (active shift exists):
        {
            "id": "...",
            "status": "active",
            "actual_start": "2024-01-15T08:55:00Z",
            ...
        }

    Example Response (no active shift):
        null
    """
    shift = await service.get_active_shift(venue_id, employee_id)
    if shift:
        return ShiftResponse.model_validate(shift)
    return None


# ---------------------------------------------------------------------------
# GET /pos/shifts/{shift_id} - Get shift details
# ---------------------------------------------------------------------------
@router.get(
    "/{shift_id}",
    response_model=ShiftResponse,
    summary="Get a shift by ID",
    responses={
        200: {"description": "Shift details retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Shift not found"},
    },
)
async def get_shift(
    shift_id: UUID = Path(
        ...,
        description="UUID of the shift to retrieve",
    ),
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """
    Retrieve details for a specific shift by its ID.

    Returns complete shift information including scheduled times, actual
    clock-in/clock-out times, break minutes, status, and notes.

    Args:
        shift_id: UUID of the shift to retrieve.
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse with full shift details.

    Raises:
        HTTPException 404: If the shift does not exist.

    Example Request:
        GET /pos/shifts/550e8400-e29b-41d4-a716-446655440000
    """
    shift = await service.get_shift(shift_id)
    return ShiftResponse.model_validate(shift)


# ---------------------------------------------------------------------------
# PATCH /pos/shifts/{shift_id} - Update shift
# ---------------------------------------------------------------------------
@router.patch(
    "/{shift_id}",
    response_model=ShiftResponse,
    summary="Update a shift",
    responses={
        200: {"description": "Shift updated successfully"},
        400: {"description": "Invalid update data or shift state"},
        401: {"description": "Authentication required"},
        404: {"description": "Shift not found"},
    },
)
async def update_shift(
    shift_id: UUID = Path(
        ...,
        description="UUID of the shift to update",
    ),
    data: ShiftUpdate = ...,
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """
    Update an existing shift with new information.

    Allows modification of shift details such as scheduled times, employee
    name, break minutes, and notes. Only non-null fields in the request
    will be updated.

    Args:
        shift_id: UUID of the shift to update.
        data: ShiftUpdate schema with fields to modify:
            - employee_name: Updated employee display name
            - scheduled_start: Updated scheduled start time
            - scheduled_end: Updated scheduled end time
            - actual_start: Manually set actual start time
            - actual_end: Manually set actual end time
            - status: Force status change (use specific endpoints preferred)
            - break_minutes: Update recorded break time
            - notes: Update shift notes
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse with updated shift details.

    Raises:
        HTTPException 404: If the shift does not exist.
        HTTPException 400: If the update is invalid for current shift state.

    Note:
        For status transitions, prefer using the dedicated endpoints:
        - POST /shifts/{id}/start for clock-in
        - POST /shifts/{id}/end for clock-out
        - POST /shifts/{id}/cancel for cancellation

    Example Request:
        PATCH /pos/shifts/550e8400-e29b-41d4-a716-446655440000
        {
            "notes": "Extended shift for inventory",
            "scheduled_end": "2024-01-15T19:00:00Z"
        }
    """
    shift = await service.update_shift(shift_id, data)
    return ShiftResponse.model_validate(shift)


# ---------------------------------------------------------------------------
# POST /pos/shifts/{shift_id}/start - Clock in
# ---------------------------------------------------------------------------
@router.post(
    "/{shift_id}/start",
    response_model=ShiftResponse,
    summary="Start a shift (clock-in)",
    responses={
        200: {"description": "Shift started successfully"},
        400: {"description": "Shift cannot be started (wrong status)"},
        401: {"description": "Authentication required"},
        404: {"description": "Shift not found"},
        409: {"description": "Employee already has an active shift"},
    },
)
async def start_shift(
    shift_id: UUID = Path(
        ...,
        description="UUID of the shift to start",
    ),
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """
    Start a scheduled shift (employee clock-in).

    Transitions a SCHEDULED shift to ACTIVE status and records the actual
    start time. Validates that the shift hasn't already been started and
    that the employee doesn't have another active shift.

    Args:
        shift_id: UUID of the shift to start.
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse with:
        - Status changed to "active"
        - actual_start set to current timestamp

    Raises:
        HTTPException 404: If the shift does not exist.
        HTTPException 400: If shift is not in SCHEDULED status
            (already active, completed, or cancelled).
        HTTPException 409: If the employee already has an active shift.

    Side Effects:
        - Publishes shift start event via event publisher
        - Logs clock-in for reporting

    Example Request:
        POST /pos/shifts/550e8400-e29b-41d4-a716-446655440000/start

    Example Response:
        {
            "id": "...",
            "status": "active",
            "actual_start": "2024-01-15T08:55:32Z",
            ...
        }
    """
    shift = await service.start_shift(shift_id)
    return ShiftResponse.model_validate(shift)


# ---------------------------------------------------------------------------
# POST /pos/shifts/{shift_id}/end - Clock out
# ---------------------------------------------------------------------------
@router.post(
    "/{shift_id}/end",
    response_model=ShiftResponse,
    summary="End a shift (clock-out)",
    responses={
        200: {"description": "Shift ended successfully"},
        400: {"description": "Shift cannot be ended (not active)"},
        401: {"description": "Authentication required"},
        404: {"description": "Shift not found"},
    },
)
async def end_shift(
    shift_id: UUID = Path(
        ...,
        description="UUID of the shift to end",
    ),
    break_minutes: int = Query(
        0,
        ge=0,
        description="Total break time in minutes to record for this shift",
    ),
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """
    End an active shift (employee clock-out).

    Transitions an ACTIVE shift to COMPLETED status, records the actual
    end time, and stores the total break time. The shift must be currently
    active to be ended.

    Args:
        shift_id: UUID of the shift to end.
        break_minutes: Total break time in minutes (default: 0). This is
            subtracted from total time when calculating worked hours.
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse with:
        - Status changed to "completed"
        - actual_end set to current timestamp
        - break_minutes recorded

    Raises:
        HTTPException 404: If the shift does not exist.
        HTTPException 400: If shift is not in ACTIVE status
            (still scheduled, already completed, or cancelled).

    Side Effects:
        - Publishes shift end event via event publisher
        - Calculates and logs total worked hours

    Example Request:
        POST /pos/shifts/550e8400-e29b-41d4-a716-446655440000/end?break_minutes=30

    Example Response:
        {
            "id": "...",
            "status": "completed",
            "actual_start": "2024-01-15T08:55:32Z",
            "actual_end": "2024-01-15T17:02:15Z",
            "break_minutes": 30,
            ...
        }
    """
    shift = await service.end_shift(shift_id, break_minutes)
    return ShiftResponse.model_validate(shift)


# ---------------------------------------------------------------------------
# POST /pos/shifts/{shift_id}/cancel - Cancel shift
# ---------------------------------------------------------------------------
@router.post(
    "/{shift_id}/cancel",
    response_model=ShiftResponse,
    summary="Cancel a scheduled shift",
    responses={
        200: {"description": "Shift cancelled successfully"},
        400: {"description": "Shift cannot be cancelled (already active/completed)"},
        401: {"description": "Authentication required"},
        404: {"description": "Shift not found"},
    },
)
async def cancel_shift(
    shift_id: UUID = Path(
        ...,
        description="UUID of the shift to cancel",
    ),
    reason: Optional[str] = Query(
        None,
        max_length=500,
        description="Optional reason for cancellation (added to notes)",
    ),
    current_user: dict = Depends(get_current_user),
    service: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """
    Cancel a scheduled shift.

    Transitions a SCHEDULED shift to CANCELLED status. Only shifts that
    haven't been started can be cancelled. Active shifts must be ended
    instead; completed shifts cannot be modified.

    Args:
        shift_id: UUID of the shift to cancel.
        reason: Optional cancellation reason (appended to shift notes).
        current_user: Authenticated user from JWT token.
        service: Injected ShiftService instance.

    Returns:
        ShiftResponse with:
        - Status changed to "cancelled"
        - Cancellation reason appended to notes (if provided)

    Raises:
        HTTPException 404: If the shift does not exist.
        HTTPException 400: If shift is ACTIVE (must end instead),
            COMPLETED, or already CANCELLED.

    Note:
        If the shift is currently active and needs to be removed from
        the schedule, use the end_shift endpoint instead.

    Example Request:
        POST /pos/shifts/550e8400-e29b-41d4-a716-446655440000/cancel?reason=Employee%20called%20out%20sick

    Example Response:
        {
            "id": "...",
            "status": "cancelled",
            "notes": "Cancellation reason: Employee called out sick",
            ...
        }
    """
    shift = await service.cancel_shift(shift_id, reason)
    return ShiftResponse.model_validate(shift)
