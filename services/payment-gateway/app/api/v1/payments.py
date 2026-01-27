"""
=============================================================================
FILE: api/v1/payments.py
PURPOSE: Payment processing API endpoints
=============================================================================
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, VenueAccessChecker
from app.models.payment import TransactionStatus
from app.schemas.payment import (
    ChargeRequest,
    AuthorizeRequest,
    CaptureRequest,
    VoidRequest,
    RefundRequest,
    PaymentResponse,
    PaymentDetailResponse,
    PaymentListResponse,
    RefundResponse,
    RefundListResponse,
    PaginationParams,
)
from app.services import PaymentService, RefundService, EventPublisher, EventType

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/charge",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process a payment charge",
)
async def charge_payment(
    request: ChargeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """
    Process a payment charge.

    - **venue_id**: The venue processing the payment
    - **amount**: Payment amount (must be > 0)
    - **currency**: Currency code (default: USD)
    - **payment_method_id**: Existing payment method ID, OR
    - **token**: One-time payment token from frontend
    """
    service = PaymentService(db)
    event_pub = EventPublisher()

    try:
        result = await service.charge(
            request=request,
            user_id=UUID(current_user["user_id"]),
        )

        # Publish event
        if result.status == TransactionStatus.COMPLETED:
            await event_pub.publish_payment_completed(
                transaction_id=result.id,
                venue_id=result.venue_id,
                customer_id=result.customer_id,
                amount=result.amount,
                currency=result.currency,
                payment_method_id=result.payment_method_id,
                order_id=request.order_id,
                metadata=request.metadata,
            )
        elif result.status == TransactionStatus.FAILED:
            await event_pub.publish_payment_failed(
                transaction_id=result.id,
                venue_id=result.venue_id,
                customer_id=result.customer_id,
                amount=result.amount,
                error_code=result.error_code,
                error_message=result.error_message,
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/authorize",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Authorize a payment for later capture",
)
async def authorize_payment(
    request: AuthorizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """
    Authorize a payment without capturing immediately.

    Use this for pre-authorizations where you want to capture the funds later.
    """
    service = PaymentService(db)

    try:
        return await service.authorize(
            request=request,
            user_id=UUID(current_user["user_id"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{transaction_id}/capture",
    response_model=PaymentResponse,
    summary="Capture an authorized payment",
)
async def capture_payment(
    transaction_id: UUID,
    request: CaptureRequest = CaptureRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Capture a previously authorized payment.

    - **amount**: Optional partial capture amount. If not provided, captures full amount.
    """
    service = PaymentService(db)

    try:
        return await service.capture(
            transaction_id=transaction_id,
            request=request,
            user_id=UUID(current_user["user_id"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{transaction_id}/void",
    response_model=PaymentResponse,
    summary="Void a payment",
)
async def void_payment(
    transaction_id: UUID,
    request: VoidRequest = VoidRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Void a payment before settlement.

    Can only void payments that are authorized or pending.
    """
    service = PaymentService(db)

    try:
        return await service.void(
            transaction_id=transaction_id,
            reason=request.reason,
            user_id=UUID(current_user["user_id"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{transaction_id}/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Refund a payment",
)
async def refund_payment(
    transaction_id: UUID,
    request: RefundRequest = RefundRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Process a refund for a completed payment.

    - **amount**: Optional partial refund amount. If not provided, refunds full remaining amount.
    - **reason**: Reason for the refund
    """
    service = RefundService(db)
    event_pub = EventPublisher()

    try:
        result = await service.create_refund(
            transaction_id=transaction_id,
            request=request,
            user_id=UUID(current_user["user_id"]),
        )

        if result.status.value == "completed":
            # Get transaction for venue_id
            payment_service = PaymentService(db)
            tx = await payment_service.get_transaction(transaction_id)
            await event_pub.publish_refund_completed(
                refund_id=result.id,
                transaction_id=transaction_id,
                venue_id=tx.venue_id,
                customer_id=tx.customer_id,
                amount=result.refund_amount,
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{transaction_id}",
    response_model=PaymentDetailResponse,
    summary="Get payment details",
)
async def get_payment(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get detailed information about a payment including refunds and disputes."""
    service = PaymentService(db)

    try:
        return await service.get_transaction(transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/",
    response_model=PaymentListResponse,
    summary="List payments",
)
async def list_payments(
    venue_id: UUID,
    customer_id: Optional[UUID] = None,
    status: Optional[TransactionStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = "created_at",
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """List payments for a venue with filters and pagination."""
    service = PaymentService(db)

    params = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return await service.list_transactions(
        venue_id=venue_id,
        params=params,
        customer_id=customer_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/{transaction_id}/refunds",
    response_model=RefundListResponse,
    summary="List refunds for a payment",
)
async def list_payment_refunds(
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all refunds for a specific payment."""
    # First get the payment to get venue_id
    payment_service = PaymentService(db)
    try:
        payment = await payment_service.get_transaction(transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    refund_service = RefundService(db)
    return await refund_service.list_refunds(
        venue_id=payment.venue_id,
        transaction_id=transaction_id,
    )
