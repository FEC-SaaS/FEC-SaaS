"""
=============================================================================
FILE: api/v1/visits.py
PURPOSE: Visit tracking API endpoints
=============================================================================
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.services.visit_service import VisitService
from app.schemas.customer import (
    VisitCreate,
    VisitUpdate,
    VisitCheckout,
    VisitResponse,
    VisitDetailResponse,
    VisitListResponse,
    ActivityCreate,
    ActivityResponse,
    PaginationParams,
)
from app.models.customer import VisitSource

# OpenAPI Tags
TAGS = ["Visits"]

router = APIRouter(tags=TAGS)


@router.get(
    "/",
    response_model=VisitListResponse,
    summary="List visits",
    description="""
    Retrieve a paginated list of customer visits for a venue.

    **Filtering options:**
    - **customer_id**: Filter visits for a specific customer
    - **date_from/date_to**: Filter by date range
    - **source**: Filter by visit source (WALK_IN, BOOKING, PARTY, MEMBERSHIP, EVENT)

    Visit records track:
    - Check-in and checkout times
    - Guest counts (adults, children)
    - Total spend
    - Activities participated in
    - Satisfaction scores

    **Events published:** `visit.checked_in`, `visit.checked_out`
    """,
    responses={
        200: {"description": "List of visits with pagination info"},
        401: {"description": "Unauthorized"},
    },
)
async def list_visits(
    venue_id: UUID,
    customer_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source: Optional[VisitSource] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("check_in_time"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List visits with filtering and pagination."""
    service = VisitService(db)
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    visits, total = await service.list_visits(
        venue_id=venue_id,
        pagination=pagination,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )

    total_pages = (total + page_size - 1) // page_size

    return VisitListResponse(
        visits=[VisitResponse.model_validate(v) for v in visits],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new visit (check-in)",
    description="""
    Record a new customer visit (check-in).

    **Required:**
    - customer_id: The customer checking in
    - venue_id: The venue being visited
    - check_in_time: When the customer arrived

    **Optional:**
    - source: Visit source (WALK_IN, BOOKING, PARTY, MEMBERSHIP, EVENT)
    - guest_count: Total guests in the party
    - child_count / adult_count: Breakdown by age group
    - booking_id: Link to booking if applicable
    - activities: List of activities to pre-register

    **Side effects:**
    - Updates customer LTV metrics
    - Updates churn risk (resets days since last visit)
    - Publishes `visit.checked_in` event
    """,
    responses={
        201: {"description": "Visit created successfully"},
        404: {"description": "Customer not found"},
        422: {"description": "Validation error"},
    },
)
async def create_visit(
    visit_data: VisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Record a new customer visit."""
    service = VisitService(db)
    visit = await service.create_visit(visit_data)
    return VisitResponse.model_validate(visit)


@router.get(
    "/{visit_id}",
    response_model=VisitDetailResponse,
    summary="Get visit details",
    description="""
    Retrieve detailed information about a specific visit.

    Returns:
    - Visit metadata (times, guests, source)
    - Total spend and satisfaction score
    - List of activities during the visit
    - Calculated duration in minutes
    """,
    responses={
        200: {"description": "Visit details"},
        404: {"description": "Visit not found"},
    },
)
async def get_visit(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get visit details by ID."""
    service = VisitService(db)
    visit = await service.get_visit(visit_id)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    response = VisitDetailResponse.model_validate(visit)
    response.duration_minutes = visit.duration_minutes
    return response


@router.put(
    "/{visit_id}",
    response_model=VisitResponse,
    summary="Update visit",
    description="""
    Update visit information.

    Can be used to:
    - Correct guest counts
    - Update notes
    - Adjust recorded times
    - Update total spend (if not using checkout flow)

    Only provided fields will be updated.
    """,
    responses={
        200: {"description": "Visit updated successfully"},
        404: {"description": "Visit not found"},
    },
)
async def update_visit(
    visit_id: UUID,
    update_data: VisitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update visit information."""
    service = VisitService(db)
    visit = await service.update_visit(visit_id, update_data)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    return VisitResponse.model_validate(visit)


@router.patch(
    "/{visit_id}/checkout",
    response_model=VisitResponse,
    summary="Check out a visit",
    description="""
    Complete a customer visit by recording checkout.

    **Optional checkout data:**
    - check_out_time: Defaults to current time if not provided
    - total_spend: Final spend amount
    - satisfaction_score: Customer satisfaction rating (1-5)
    - feedback: Customer feedback text

    **Side effects:**
    - Updates customer LTV metrics (revenue, avg spend, frequency)
    - Updates churn risk calculations
    - Publishes `visit.checked_out` event

    This is the recommended way to finalize a visit as it properly
    triggers all analytics updates.
    """,
    responses={
        200: {"description": "Visit checked out successfully"},
        404: {"description": "Visit not found"},
    },
)
async def checkout_visit(
    visit_id: UUID,
    checkout_data: VisitCheckout,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check out a customer visit."""
    service = VisitService(db)
    visit = await service.checkout_visit(visit_id, checkout_data)

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    return VisitResponse.model_validate(visit)


@router.post(
    "/{visit_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add activity to visit",
    description="""
    Record an activity during a customer visit.

    Activities can be:
    - **ATTRACTION**: Rides, games, simulators
    - **FOOD_BEVERAGE**: Restaurant, snack bar purchases
    - **RETAIL**: Gift shop, merchandise
    - **ARCADE**: Arcade games, redemption games
    - **PARTY**: Party room activities
    - **EVENT**: Special events, shows
    - **SERVICE**: Additional services

    **Activity data includes:**
    - activity_name: Name of the activity
    - amount_spent: Money spent on this activity
    - duration_minutes: Time spent
    - satisfaction_score: Rating for this activity

    Adding activities automatically updates the visit's total spend.
    """,
    responses={
        201: {"description": "Activity added successfully"},
        404: {"description": "Visit not found"},
    },
)
async def add_activity(
    visit_id: UUID,
    activity_data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add an activity to a visit."""
    activity_data.visit_id = visit_id
    service = VisitService(db)
    activity = await service.add_activity(activity_data)
    return ActivityResponse.model_validate(activity)


@router.get(
    "/customer/{customer_id}",
    summary="Get customer's recent visits",
    description="""
    Retrieve the most recent visits for a specific customer.

    Returns visits ordered by check-in time (most recent first).
    Each visit includes:
    - Visit metadata and timing
    - Activities during the visit
    - Spend and satisfaction data

    Useful for:
    - Customer profile views
    - Visit history reports
    - Customer service lookups
    """,
    responses={
        200: {"description": "List of recent visits"},
        404: {"description": "Customer not found"},
    },
)
async def get_customer_visits(
    customer_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get recent visits for a customer."""
    service = VisitService(db)
    visits = await service.get_customer_visits(customer_id, limit)
    return [VisitDetailResponse.model_validate(v) for v in visits]


@router.get(
    "/stats",
    summary="Get visit statistics",
    description="""
    Get aggregated visit statistics for a date range.

    Returns:
    - **total_visits**: Number of visits in the period
    - **unique_customers**: Number of distinct customers who visited
    - **total_revenue**: Sum of all visit spend
    - **avg_spend_per_visit**: Average spend per visit

    Use this for:
    - Dashboard metrics
    - Period-over-period comparisons
    - Revenue reporting
    """,
    responses={
        200: {"description": "Visit statistics for the period"},
    },
)
async def get_visit_stats(
    venue_id: UUID,
    date_from: date,
    date_to: date,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get visit statistics for a period."""
    service = VisitService(db)
    stats = await service.get_visit_stats(venue_id, date_from, date_to)
    return stats
