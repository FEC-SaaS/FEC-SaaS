"""Refund API routes for the POS service."""

import math
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    PaginatedResponse,
    RefundApprove,
    RefundCreate,
    RefundResponse,
)
from app.services.event_publisher import event_publisher
from app.services.refund_service import RefundService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> RefundService:
    return RefundService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/transactions/{transaction_id}/refunds — issue a refund
# ---------------------------------------------------------------------------
@router.post(
    "/pos/transactions/{transaction_id}/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a refund for a transaction",
)
async def issue_refund(
    transaction_id: UUID,
    body: RefundCreate,
    venue_id: UUID = Query(..., description="Venue that owns the transaction"),
    service: RefundService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> RefundResponse:
    """Create and issue a refund against an existing POS transaction."""
    refund = await service.issue_refund(transaction_id, venue_id, body)
    return RefundResponse.model_validate(refund)


# ---------------------------------------------------------------------------
# GET /pos/refunds/{refund_id} — get refund details
# ---------------------------------------------------------------------------
@router.get(
    "/pos/refunds/{refund_id}",
    response_model=RefundResponse,
    summary="Get refund details",
)
async def get_refund(
    refund_id: UUID,
    service: RefundService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> RefundResponse:
    """Retrieve a single refund by its ID."""
    refund = await service.get_refund(refund_id)
    if not refund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund not found",
        )
    return RefundResponse.model_validate(refund)


# ---------------------------------------------------------------------------
# GET /pos/refunds — list refunds
# ---------------------------------------------------------------------------
@router.get(
    "/pos/refunds",
    response_model=PaginatedResponse,
    summary="List refunds",
)
async def list_refunds(
    venue_id: UUID = Query(..., description="Venue to list refunds for"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by refund status"),
    date_from: Optional[datetime] = Query(None, description="Start of date range"),
    date_to: Optional[datetime] = Query(None, description="End of date range"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: RefundService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaginatedResponse:
    """Return a paginated list of refunds for a venue."""
    refunds, total = await service.list_refunds(
        venue_id=venue_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[RefundResponse.model_validate(r) for r in refunds],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


# ---------------------------------------------------------------------------
# POST /pos/refunds/{refund_id}/approve — approve a refund
# ---------------------------------------------------------------------------
@router.post(
    "/pos/refunds/{refund_id}/approve",
    response_model=RefundResponse,
    summary="Approve a refund",
)
async def approve_refund(
    refund_id: UUID,
    body: RefundApprove,
    service: RefundService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> RefundResponse:
    """Approve a pending refund request."""
    refund = await service.approve_refund(refund_id, body)
    if not refund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund not found",
        )
    return RefundResponse.model_validate(refund)


# ---------------------------------------------------------------------------
# POST /pos/refunds/{refund_id}/process — process a refund
# ---------------------------------------------------------------------------
@router.post(
    "/pos/refunds/{refund_id}/process",
    response_model=RefundResponse,
    summary="Process a refund",
)
async def process_refund(
    refund_id: UUID,
    service: RefundService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> RefundResponse:
    """Process an approved refund."""
    refund = await service.process_refund(refund_id)
    if not refund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund not found",
        )
    return RefundResponse.model_validate(refund)
