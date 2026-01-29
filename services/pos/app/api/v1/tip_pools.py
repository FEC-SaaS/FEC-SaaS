"""
Tip Pool API routes for the POS service.

This module provides REST API endpoints for managing tip pools, including:
- Creating and managing tip pools for specific shift dates
- Adding and removing participants from pools
- Adding tips to open pools
- Calculating and previewing tip distributions
- Finalizing and distributing tips to employees
- Retrieving employee tip history and summaries

All endpoints require authentication and operate within the context of a venue.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    TipDistributionCalculation,
    TipDistributionPreview,
    TipDistributionResponse,
    TipPoolAddParticipant,
    TipPoolAddTips,
    TipPoolCreate,
    TipPoolResponse,
    TipSummary,
)
from app.services.event_publisher import event_publisher
from app.services.tip_service import TipService

router = APIRouter(prefix="/pos/tip-pools")
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> TipService:
    """
    Dependency to get a TipService instance.

    Args:
        db: Database session from dependency injection.

    Returns:
        Configured TipService instance with event publisher.
    """
    return TipService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/tip-pools — create a new tip pool
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=TipPoolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tip pool",
)
async def create_tip_pool(
    venue_id: UUID = Query(..., description="Venue to create the tip pool for"),
    shift_date: date = Query(..., description="The shift date this pool covers"),
    distribution_method: str = Query(
        "hours_based",
        description="Distribution method: 'equal', 'hours_based', or 'sales_based'"
    ),
    notes: Optional[str] = Query(None, description="Optional notes about the pool"),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipPoolResponse:
    """
    Create a new tip pool for a specific shift date.

    Creates a tip pool in OPEN status that can accept tips and participants.
    Only one pool can exist per venue per shift date.

    Args:
        venue_id: UUID of the venue to create the pool for.
        shift_date: The date of the shift this pool covers.
        distribution_method: How tips will be distributed among participants.
            - "equal": Split evenly among all participants.
            - "hours_based": Distribute proportionally by hours worked.
            - "sales_based": Distribute proportionally by sales.
        notes: Optional notes about the tip pool.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The newly created TipPoolResponse.

    Raises:
        HTTPException 409: If a pool already exists for this venue and date.
    """
    tip_pool = await service.create_tip_pool(
        venue_id=venue_id,
        shift_date=shift_date,
        distribution_method=distribution_method,
        notes=notes,
    )
    return TipPoolResponse.model_validate(tip_pool)


# ---------------------------------------------------------------------------
# GET /pos/tip-pools/{pool_id} — get a tip pool by ID
# ---------------------------------------------------------------------------
@router.get(
    "/{pool_id}",
    response_model=TipPoolResponse,
    summary="Get a tip pool by ID",
)
async def get_tip_pool(
    pool_id: UUID,
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipPoolResponse:
    """
    Retrieve a tip pool by its unique identifier.

    Args:
        pool_id: UUID of the tip pool to retrieve.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The TipPoolResponse for the requested pool.

    Raises:
        HTTPException 404: If the tip pool is not found.
    """
    tip_pool = await service.get_tip_pool(pool_id)
    return TipPoolResponse.model_validate(tip_pool)


# ---------------------------------------------------------------------------
# GET /pos/tip-pools — list tip pools for a venue
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[TipPoolResponse],
    summary="List tip pools for a venue",
)
async def list_tip_pools(
    venue_id: UUID = Query(..., description="Venue to list tip pools for"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by pool status: 'open', 'closed', or 'distributed'"
    ),
    date_from: Optional[date] = Query(
        None,
        description="Filter for pools on or after this date"
    ),
    date_to: Optional[date] = Query(
        None,
        description="Filter for pools on or before this date"
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[TipPoolResponse]:
    """
    List tip pools for a venue with optional filtering and pagination.

    Supports filtering by status and date range, with pagination controls.

    Args:
        venue_id: UUID of the venue to list pools for.
        status_filter: Optional filter by pool status.
        date_from: Optional start date filter (inclusive).
        date_to: Optional end date filter (inclusive).
        skip: Number of records to skip for pagination.
        limit: Maximum number of records to return.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        List of TipPoolResponse objects matching the criteria.
    """
    # Calculate page from skip/limit
    page = (skip // limit) + 1 if limit > 0 else 1

    pools, total = await service.list_tip_pools(
        venue_id=venue_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=limit,
    )
    return [TipPoolResponse.model_validate(p) for p in pools]


# ---------------------------------------------------------------------------
# POST /pos/tip-pools/{pool_id}/tips — add tips to a pool
# ---------------------------------------------------------------------------
@router.post(
    "/{pool_id}/tips",
    response_model=TipPoolResponse,
    summary="Add tips to an open pool",
)
async def add_tips(
    pool_id: UUID,
    amount: Decimal = Query(..., gt=0, description="Amount of tips to add"),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipPoolResponse:
    """
    Add tips to an open tip pool.

    Tips can only be added to pools in OPEN status. Once a pool is closed
    or distributed, no additional tips can be added.

    Args:
        pool_id: UUID of the tip pool to add tips to.
        amount: The amount of tips to add (must be positive).
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated TipPoolResponse with new total.

    Raises:
        HTTPException 404: If the tip pool is not found.
        HTTPException 400: If the pool is already closed or distributed.
    """
    tip_pool = await service.add_tips_to_pool(pool_id, amount)
    return TipPoolResponse.model_validate(tip_pool)


# ---------------------------------------------------------------------------
# POST /pos/tip-pools/{pool_id}/participants — add a participant
# ---------------------------------------------------------------------------
@router.post(
    "/{pool_id}/participants",
    response_model=TipPoolResponse,
    summary="Add a participant to the pool",
)
async def add_participant(
    pool_id: UUID,
    employee_id: UUID = Query(..., description="Employee's unique identifier"),
    employee_name: str = Query(..., description="Employee's display name"),
    hours_worked: Decimal = Query(..., ge=0, description="Hours worked during the shift"),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipPoolResponse:
    """
    Add or update a participant in the tip pool.

    If the employee is already in the pool, their hours will be updated.
    Otherwise, they are added as a new participant.

    Args:
        pool_id: UUID of the tip pool.
        employee_id: The employee's unique identifier.
        employee_name: The employee's display name.
        hours_worked: The number of hours worked during the shift.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated TipPoolResponse with the participant added/updated.

    Raises:
        HTTPException 404: If the tip pool is not found.
        HTTPException 400: If the pool is already closed or distributed.
    """
    tip_pool = await service.add_participant(
        pool_id=pool_id,
        employee_id=employee_id,
        employee_name=employee_name,
        hours_worked=hours_worked,
    )
    return TipPoolResponse.model_validate(tip_pool)


# ---------------------------------------------------------------------------
# DELETE /pos/tip-pools/{pool_id}/participants/{employee_id} — remove participant
# ---------------------------------------------------------------------------
@router.delete(
    "/{pool_id}/participants/{employee_id}",
    response_model=TipPoolResponse,
    summary="Remove a participant from the pool",
)
async def remove_participant(
    pool_id: UUID,
    employee_id: UUID,
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipPoolResponse:
    """
    Remove a participant from the tip pool.

    Participants can only be removed from pools in OPEN status.

    Args:
        pool_id: UUID of the tip pool.
        employee_id: The employee's unique identifier to remove.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated TipPoolResponse with the participant removed.

    Raises:
        HTTPException 404: If the tip pool is not found.
        HTTPException 400: If the pool is already closed or distributed.
    """
    tip_pool = await service.remove_participant(pool_id, employee_id)
    return TipPoolResponse.model_validate(tip_pool)


# ---------------------------------------------------------------------------
# POST /pos/tip-pools/{pool_id}/close — close the tip pool
# ---------------------------------------------------------------------------
@router.post(
    "/{pool_id}/close",
    response_model=TipPoolResponse,
    summary="Close the tip pool",
)
async def close_pool(
    pool_id: UUID,
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipPoolResponse:
    """
    Close a tip pool, preventing further modifications.

    A closed pool can still be distributed but cannot accept new tips
    or participants. This is typically done at the end of a shift
    before calculating final distributions.

    Args:
        pool_id: UUID of the tip pool to close.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated TipPoolResponse in CLOSED status.

    Raises:
        HTTPException 404: If the tip pool is not found.
        HTTPException 400: If the pool is already closed or distributed.
    """
    tip_pool = await service.close_pool(pool_id)
    return TipPoolResponse.model_validate(tip_pool)


# ---------------------------------------------------------------------------
# GET /pos/tip-pools/{pool_id}/calculate — preview distribution
# ---------------------------------------------------------------------------
@router.get(
    "/{pool_id}/calculate",
    response_model=TipDistributionCalculation,
    summary="Preview tip distribution without committing",
)
async def calculate_distribution(
    pool_id: UUID,
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipDistributionCalculation:
    """
    Calculate and preview tip distribution without committing.

    This method calculates how tips would be distributed based on the
    pool's distribution method, allowing managers to review before
    finalizing. No database changes are made.

    Args:
        pool_id: UUID of the tip pool to calculate.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        TipDistributionCalculation with preview of each employee's share.

    Raises:
        HTTPException 404: If the tip pool is not found.
        HTTPException 400: If the pool has no participants or is already distributed.
    """
    tip_pool = await service.get_tip_pool(pool_id)
    distributions = await service.calculate_distribution(pool_id)

    # Calculate total hours from participants
    participants = tip_pool.pool_participants or []
    total_hours = sum(Decimal(p.get("hours_worked", "0")) for p in participants)

    return TipDistributionCalculation(
        pool_id=pool_id,
        total_tips=tip_pool.total_tips,
        distribution_method=tip_pool.distribution_method,
        total_hours=total_hours,
        participant_count=len(participants),
        distributions=[
            TipDistributionPreview(
                employee_id=UUID(d["employee_id"]),
                employee_name=d["employee_name"],
                hours_worked=d["hours_worked"],
                tip_amount=d["tip_amount"],
                percentage=d["percentage"],
            )
            for d in distributions
        ],
    )


# ---------------------------------------------------------------------------
# POST /pos/tip-pools/{pool_id}/distribute — finalize and distribute tips
# ---------------------------------------------------------------------------
@router.post(
    "/{pool_id}/distribute",
    response_model=List[TipDistributionResponse],
    summary="Finalize and distribute tips",
)
async def distribute_tips(
    pool_id: UUID,
    distributed_by: UUID = Query(
        ...,
        description="UUID of the user authorizing the distribution"
    ),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[TipDistributionResponse]:
    """
    Finalize and execute tip distribution.

    Calculates the distribution, creates TipDistribution records for each
    participant, and marks the pool as distributed. This action is
    irreversible.

    Args:
        pool_id: UUID of the tip pool to distribute.
        distributed_by: UUID of the user authorizing the distribution.
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        List of TipDistributionResponse for each participant.

    Raises:
        HTTPException 404: If the tip pool is not found.
        HTTPException 400: If the pool has no participants or is already distributed.
    """
    distributions = await service.distribute_tips(pool_id, distributed_by)
    return [TipDistributionResponse.model_validate(d) for d in distributions]


# ---------------------------------------------------------------------------
# GET /pos/tip-pools/employee/{employee_id}/tips — get employee tip history
# ---------------------------------------------------------------------------
@router.get(
    "/employee/{employee_id}/tips",
    response_model=List[TipDistributionResponse],
    summary="Get tip distributions for an employee",
)
async def get_employee_tips(
    employee_id: UUID,
    venue_id: UUID = Query(..., description="Venue to filter by"),
    date_from: date = Query(..., description="Start date of range (inclusive)"),
    date_to: date = Query(..., description="End date of range (inclusive)"),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[TipDistributionResponse]:
    """
    Get tip distributions for a specific employee within a date range.

    Returns all tip distributions the employee has received from distributed
    pools within the specified date range.

    Args:
        employee_id: UUID of the employee to get tips for.
        venue_id: UUID of the venue to filter by.
        date_from: Start date of the range (inclusive).
        date_to: End date of the range (inclusive).
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        List of TipDistributionResponse for the employee.
    """
    distributions = await service.get_employee_tips(
        venue_id=venue_id,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
    )
    return [TipDistributionResponse.model_validate(d) for d in distributions]


# ---------------------------------------------------------------------------
# GET /pos/tip-pools/summary — get tip summary for a date range
# ---------------------------------------------------------------------------
@router.get(
    "/summary",
    response_model=TipSummary,
    summary="Get tip summary for a date range",
)
async def get_tip_summary(
    venue_id: UUID = Query(..., description="Venue to summarize"),
    date_from: date = Query(..., description="Start date of range (inclusive)"),
    date_to: date = Query(..., description="End date of range (inclusive)"),
    service: TipService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TipSummary:
    """
    Get a summary of tip activity for a venue within a date range.

    Provides aggregate statistics including total pools, tips collected
    and distributed, participant counts, and averages.

    Args:
        venue_id: UUID of the venue to summarize.
        date_from: Start date of the range (inclusive).
        date_to: End date of the range (inclusive).
        service: Injected TipService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        TipSummary with aggregate statistics.
    """
    summary_data = await service.get_tip_summary(venue_id, date_from, date_to)

    return TipSummary(
        venue_id=UUID(summary_data["venue_id"]),
        date_from=date.fromisoformat(summary_data["date_from"]),
        date_to=date.fromisoformat(summary_data["date_to"]),
        total_pools=summary_data["total_pools"],
        total_tips_collected=Decimal(summary_data["total_tips_collected"]),
        total_tips_distributed=Decimal(summary_data["total_tips_distributed"]),
        total_participants=summary_data["total_participants"],
        pools_by_status=summary_data["pools_by_status"],
        average_tip_per_pool=Decimal(summary_data["average_tip_per_pool"]),
        average_tip_per_employee=Decimal(summary_data["average_tip_per_employee"]),
    )
