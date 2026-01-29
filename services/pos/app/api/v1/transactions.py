"""POS transaction API routes."""

import math
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import TransactionStatus, TransactionType
from app.schemas.pos import (
    PaginatedResponse,
    TransactionCreate,
    TransactionResponse,
)
from app.services.event_publisher import event_publisher
from app.services.transaction_service import TransactionService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> TransactionService:
    return TransactionService(db, event_publisher)


# ---------------------------------------------------------------------------
# GET /pos/transactions — list transactions
# ---------------------------------------------------------------------------
@router.get(
    "/pos/transactions",
    response_model=PaginatedResponse,
    summary="List POS transactions",
)
async def list_transactions(
    venue_id: UUID = Query(..., description="Venue to list transactions for"),
    transaction_type: Optional[TransactionType] = Query(None),
    status_filter: Optional[TransactionStatus] = Query(None, alias="status"),
    date_from: Optional[datetime] = Query(None, alias="date_from"),
    date_to: Optional[datetime] = Query(None, alias="date_to"),
    customer_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: TransactionService = Depends(_get_service),
):
    """List POS transactions with optional filtering and pagination."""
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    transaction_type_val = transaction_type.value if transaction_type else None
    status_val = status_filter.value if status_filter else None
    items, total = await service.list_transactions(
        venue_id,
        transaction_type_val,
        status_val,
        date_from,
        date_to,
        customer_id,
        page,
        page_size,
    )
    return PaginatedResponse(
        items=[TransactionResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


# ---------------------------------------------------------------------------
# POST /pos/transactions — create transaction
# ---------------------------------------------------------------------------
@router.post(
    "/pos/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a POS transaction",
)
async def create_transaction(
    venue_id: UUID = Query(..., description="Venue that owns the transaction"),
    body: TransactionCreate = ...,
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
    service: TransactionService = Depends(_get_service),
):
    """Create a new POS transaction for a venue."""
    transaction = await service.create_transaction(
        venue_id, body, idempotency_key=idempotency_key
    )
    return TransactionResponse.model_validate(transaction)


# ---------------------------------------------------------------------------
# GET /pos/transactions/summary — transaction summary
# ---------------------------------------------------------------------------
@router.get(
    "/pos/transactions/summary",
    response_model=Dict[str, dict],
    summary="Transaction summary",
)
async def get_transaction_summary(
    venue_id: UUID = Query(..., description="Venue to summarise"),
    date_from: datetime = Query(..., alias="date_from", description="Start of date range"),
    date_to: datetime = Query(..., alias="date_to", description="End of date range"),
    current_user: dict = Depends(get_current_user),
    service: TransactionService = Depends(_get_service),
):
    """Return a transaction summary for a venue and date range."""
    return await service.get_transaction_summary(venue_id, date_from, date_to)


# ---------------------------------------------------------------------------
# GET /pos/transactions/{transaction_id} — get transaction details
# ---------------------------------------------------------------------------
@router.get(
    "/pos/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction details",
)
async def get_transaction(
    transaction_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: TransactionService = Depends(_get_service),
):
    """Retrieve details for a specific POS transaction."""
    result = await service.get_transaction(transaction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse.model_validate(result)


# ---------------------------------------------------------------------------
# PATCH /pos/transactions/{transaction_id}/void — void transaction
# ---------------------------------------------------------------------------
@router.patch(
    "/pos/transactions/{transaction_id}/void",
    response_model=TransactionResponse,
    summary="Void a transaction",
)
async def void_transaction(
    transaction_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: TransactionService = Depends(_get_service),
):
    """Void an existing POS transaction."""
    result = await service.void_transaction(transaction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse.model_validate(result)


# ---------------------------------------------------------------------------
# PATCH /pos/transactions/{transaction_id}/complete — complete transaction
# ---------------------------------------------------------------------------
@router.patch(
    "/pos/transactions/{transaction_id}/complete",
    response_model=TransactionResponse,
    summary="Complete a transaction",
)
async def complete_transaction(
    transaction_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: TransactionService = Depends(_get_service),
):
    """Mark a POS transaction as completed."""
    result = await service.complete_transaction(transaction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse.model_validate(result)
