"""Receipt API routes for the POS service."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    ReceiptEmailRequest,
    ReceiptGenerateRequest,
    ReceiptResponse,
)
from app.services.event_publisher import event_publisher
from app.services.receipt_service import ReceiptService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> ReceiptService:
    return ReceiptService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/transactions/{transaction_id}/receipts — generate receipt
# ---------------------------------------------------------------------------
@router.post(
    "/pos/transactions/{transaction_id}/receipts",
    response_model=ReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a receipt for a transaction",
)
async def generate_receipt(
    transaction_id: UUID,
    body: ReceiptGenerateRequest,
    venue_id: UUID = Query(..., description="Venue that owns the transaction"),
    service: ReceiptService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReceiptResponse:
    """Generate a new receipt for an existing POS transaction."""
    receipt = await service.generate_receipt(transaction_id, venue_id, body)
    return ReceiptResponse.model_validate(receipt)


# ---------------------------------------------------------------------------
# GET /pos/receipts/{receipt_id} — get receipt
# ---------------------------------------------------------------------------
@router.get(
    "/pos/receipts/{receipt_id}",
    response_model=ReceiptResponse,
    summary="Get receipt details",
)
async def get_receipt(
    receipt_id: UUID,
    service: ReceiptService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReceiptResponse:
    """Retrieve a single receipt by its ID."""
    receipt = await service.get_receipt(receipt_id)
    return ReceiptResponse.model_validate(receipt)


# ---------------------------------------------------------------------------
# GET /pos/receipts/by-number/{receipt_number} — get receipt by number
# ---------------------------------------------------------------------------
@router.get(
    "/pos/receipts/by-number/{receipt_number}",
    response_model=ReceiptResponse,
    summary="Get receipt by receipt number",
)
async def get_receipt_by_number(
    receipt_number: str,
    service: ReceiptService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReceiptResponse:
    """Retrieve a receipt by its unique receipt number (e.g. FEC-20260128-AB12CD)."""
    receipt = await service.get_receipt_by_number(receipt_number)
    return ReceiptResponse.model_validate(receipt)


# ---------------------------------------------------------------------------
# POST /pos/receipts/{receipt_id}/email — email receipt
# ---------------------------------------------------------------------------
@router.post(
    "/pos/receipts/{receipt_id}/email",
    response_model=ReceiptResponse,
    summary="Email a receipt",
)
async def email_receipt(
    receipt_id: UUID,
    body: ReceiptEmailRequest,
    service: ReceiptService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReceiptResponse:
    """Send a receipt to a customer via email."""
    receipt = await service.email_receipt(receipt_id, body)
    return ReceiptResponse.model_validate(receipt)


# ---------------------------------------------------------------------------
# POST /pos/receipts/{receipt_id}/print — mark receipt as printed
# ---------------------------------------------------------------------------
@router.post(
    "/pos/receipts/{receipt_id}/print",
    response_model=ReceiptResponse,
    summary="Mark receipt as printed",
)
async def mark_receipt_printed(
    receipt_id: UUID,
    service: ReceiptService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> ReceiptResponse:
    """Mark an existing receipt as printed by setting its printed_at timestamp."""
    receipt = await service.mark_printed(receipt_id)
    return ReceiptResponse.model_validate(receipt)
