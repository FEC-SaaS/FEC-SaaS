"""Payment API routes for the POS service."""

from datetime import datetime
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import PaymentCreate, PaymentResponse
from app.services.event_publisher import event_publisher
from app.services.payment_service import PaymentService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/transactions/{transaction_id}/payments — process payment
# ---------------------------------------------------------------------------
@router.post(
    "/pos/transactions/{transaction_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process a payment for a transaction",
)
async def process_payment(
    transaction_id: UUID,
    body: PaymentCreate,
    venue_id: UUID = Query(..., description="Venue that owns the transaction"),
    service: PaymentService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaymentResponse:
    """Create and process a payment against an existing POS transaction."""
    payment = await service.process_payment(transaction_id, venue_id, body)
    return PaymentResponse.model_validate(payment)


# ---------------------------------------------------------------------------
# GET /pos/payments/{payment_id} — get payment details
# ---------------------------------------------------------------------------
@router.get(
    "/pos/payments/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details",
)
async def get_payment(
    payment_id: UUID,
    service: PaymentService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaymentResponse:
    """Retrieve a single payment by its ID."""
    payment = await service.get_payment(payment_id)
    return PaymentResponse.model_validate(payment)


# ---------------------------------------------------------------------------
# GET /pos/transactions/{transaction_id}/payments — list payments for txn
# ---------------------------------------------------------------------------
@router.get(
    "/pos/transactions/{transaction_id}/payments",
    response_model=List[PaymentResponse],
    summary="List payments for a transaction",
)
async def list_payments_for_transaction(
    transaction_id: UUID,
    service: PaymentService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[PaymentResponse]:
    """Return all payments associated with a given transaction."""
    payments = await service.list_payments_for_transaction(transaction_id)
    return [PaymentResponse.model_validate(p) for p in payments]


# ---------------------------------------------------------------------------
# POST /pos/payments/{payment_id}/reverse — reverse a payment
# ---------------------------------------------------------------------------
@router.post(
    "/pos/payments/{payment_id}/reverse",
    response_model=PaymentResponse,
    summary="Reverse a payment",
)
async def reverse_payment(
    payment_id: UUID,
    service: PaymentService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaymentResponse:
    """Reverse a previously completed payment."""
    payment = await service.reverse_payment(payment_id)
    return PaymentResponse.model_validate(payment)


# ---------------------------------------------------------------------------
# GET /pos/payments/summary — payment method summary
# ---------------------------------------------------------------------------
@router.get(
    "/pos/payments/summary",
    response_model=Dict[str, dict],
    summary="Payment method summary",
)
async def get_payment_summary(
    venue_id: UUID = Query(..., description="Venue to summarise"),
    date_from: datetime = Query(..., description="Start of date range"),
    date_to: datetime = Query(..., description="End of date range"),
    service: PaymentService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, dict]:
    """Return a payment summary grouped by payment method for a venue and date range."""
    return await service.get_payment_summary(venue_id, date_from, date_to)
