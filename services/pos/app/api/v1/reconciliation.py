"""Reconciliation API routes for the POS service."""

import math
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    PaginatedResponse,
    ReconciliationCreate,
    ReconciliationResponse,
)
from app.services.event_publisher import event_publisher
from app.services.reconciliation_service import ReconciliationService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> ReconciliationService:
    return ReconciliationService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/reconciliation/daily — create daily reconciliation
# ---------------------------------------------------------------------------
@router.post(
    "/pos/reconciliation/daily",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create daily reconciliation",
)
async def create_daily_reconciliation(
    body: ReconciliationCreate,
    venue_id: UUID = Query(..., description="Venue to reconcile"),
    service: ReconciliationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReconciliationResponse:
    """Create an end-of-day reconciliation report for a venue."""
    reconciliation = await service.create_reconciliation(venue_id, body)
    return ReconciliationResponse.model_validate(reconciliation)


# ---------------------------------------------------------------------------
# GET /pos/reconciliation/{reconciliation_id} — get reconciliation
# ---------------------------------------------------------------------------
@router.get(
    "/pos/reconciliation/{reconciliation_id}",
    response_model=ReconciliationResponse,
    summary="Get reconciliation details",
)
async def get_reconciliation(
    reconciliation_id: UUID,
    service: ReconciliationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReconciliationResponse:
    """Retrieve a single reconciliation record by its ID."""
    reconciliation = await service.get_reconciliation(reconciliation_id)
    if not reconciliation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation not found",
        )
    return ReconciliationResponse.model_validate(reconciliation)


# ---------------------------------------------------------------------------
# GET /pos/reconciliation/daily — get reconciliation by date
# ---------------------------------------------------------------------------
@router.get(
    "/pos/reconciliation/daily",
    response_model=ReconciliationResponse,
    summary="Get reconciliation by date",
)
async def get_reconciliation_by_date(
    venue_id: UUID = Query(..., description="Venue to look up"),
    date: date = Query(..., description="Reconciliation date"),
    service: ReconciliationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReconciliationResponse:
    """Retrieve a reconciliation record for a specific venue and date."""
    reconciliation = await service.get_reconciliation_by_date(venue_id, date)
    if not reconciliation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation not found",
        )
    return ReconciliationResponse.model_validate(reconciliation)


# ---------------------------------------------------------------------------
# PATCH /pos/reconciliation/{reconciliation_id}/complete — complete
# ---------------------------------------------------------------------------
@router.patch(
    "/pos/reconciliation/{reconciliation_id}/complete",
    response_model=ReconciliationResponse,
    summary="Complete reconciliation",
)
async def complete_reconciliation(
    reconciliation_id: UUID,
    service: ReconciliationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReconciliationResponse:
    """Mark a reconciliation as completed."""
    reconciliation = await service.complete_reconciliation(reconciliation_id, current_user)
    if not reconciliation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation not found",
        )
    return ReconciliationResponse.model_validate(reconciliation)


# ---------------------------------------------------------------------------
# GET /pos/reconciliation — list reconciliations
# ---------------------------------------------------------------------------
@router.get(
    "/pos/reconciliation",
    response_model=PaginatedResponse,
    summary="List reconciliations",
)
async def list_reconciliations(
    venue_id: UUID = Query(..., description="Venue to list reconciliations for"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    date_from: Optional[datetime] = Query(None, description="Start of date range"),
    date_to: Optional[datetime] = Query(None, description="End of date range"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: ReconciliationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaginatedResponse:
    """Return a paginated list of reconciliation records for a venue."""
    reconciliations, total = await service.list_reconciliations(
        venue_id=venue_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[ReconciliationResponse.model_validate(r) for r in reconciliations],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
