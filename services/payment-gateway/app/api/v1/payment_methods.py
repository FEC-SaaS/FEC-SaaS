"""
=============================================================================
FILE: api/v1/payment_methods.py
PURPOSE: Payment method management API endpoints
=============================================================================
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.schemas.payment import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentMethodResponse,
    PaymentMethodListResponse,
)
from app.services import PaymentMethodService, EventPublisher, EventType

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])


@router.post(
    "/",
    response_model=PaymentMethodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new payment method",
)
async def create_payment_method(
    data: PaymentMethodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Add a new payment method for a customer.

    The token should be a payment method token from the frontend SDK
    (e.g., Stripe Elements, Square Web Payments SDK).
    """
    service = PaymentMethodService(db)
    event_pub = EventPublisher()

    try:
        result = await service.create_payment_method(data)

        await event_pub.publish(
            EventType.PAYMENT_METHOD_ADDED,
            payload={
                "payment_method_id": result.id,
                "customer_id": result.customer_id,
                "card_brand": result.card_brand.value if result.card_brand else None,
                "card_last_four": result.card_last_four,
            },
            venue_id=result.venue_id,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{payment_method_id}",
    response_model=PaymentMethodResponse,
    summary="Get a payment method",
)
async def get_payment_method(
    payment_method_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific payment method."""
    service = PaymentMethodService(db)

    try:
        return await service.get_payment_method(payment_method_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{payment_method_id}",
    response_model=PaymentMethodResponse,
    summary="Update a payment method",
)
async def update_payment_method(
    payment_method_id: UUID,
    data: PaymentMethodUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update payment method details like billing address or nickname."""
    service = PaymentMethodService(db)
    event_pub = EventPublisher()

    try:
        result = await service.update_payment_method(payment_method_id, data)

        await event_pub.publish(
            EventType.PAYMENT_METHOD_UPDATED,
            payload={
                "payment_method_id": result.id,
                "customer_id": result.customer_id,
            },
            venue_id=result.venue_id,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{payment_method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a payment method",
)
async def delete_payment_method(
    payment_method_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a payment method from a customer's account."""
    service = PaymentMethodService(db)
    event_pub = EventPublisher()

    try:
        # Get payment method first for event
        pm = await service.get_payment_method(payment_method_id)

        await service.delete_payment_method(payment_method_id)

        await event_pub.publish(
            EventType.PAYMENT_METHOD_REMOVED,
            payload={
                "payment_method_id": payment_method_id,
                "customer_id": pm.customer_id,
            },
            venue_id=pm.venue_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/customer/{customer_id}",
    response_model=PaymentMethodListResponse,
    summary="List customer payment methods",
)
async def list_customer_payment_methods(
    customer_id: UUID,
    venue_id: Optional[UUID] = None,
    include_expired: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all payment methods for a customer."""
    service = PaymentMethodService(db)

    return await service.list_payment_methods(
        customer_id=customer_id,
        venue_id=venue_id,
        include_expired=include_expired,
    )


@router.post(
    "/{payment_method_id}/set-default",
    response_model=PaymentMethodResponse,
    summary="Set as default payment method",
)
async def set_default_payment_method(
    payment_method_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Set a payment method as the default for a customer."""
    service = PaymentMethodService(db)

    try:
        return await service.set_default(payment_method_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/customer/{customer_id}/default",
    response_model=Optional[PaymentMethodResponse],
    summary="Get default payment method",
)
async def get_default_payment_method(
    customer_id: UUID,
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the default payment method for a customer at a venue."""
    service = PaymentMethodService(db)

    return await service.get_default_payment_method(
        customer_id=customer_id,
        venue_id=venue_id,
    )
