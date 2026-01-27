"""
=============================================================================
FILE: api/v1/subscriptions.py
PURPOSE: Subscription management API endpoints
=============================================================================
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, VenueAccessChecker
from app.models.payment import SubscriptionStatus
from app.schemas.payment import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    PaginationParams,
)
from app.services import SubscriptionService, EventPublisher, EventType

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post(
    "/",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subscription",
)
async def create_subscription(
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """
    Create a new subscription for a customer.

    - **customer_id**: Customer to subscribe
    - **venue_id**: Venue offering the subscription
    - **payment_method_id**: Payment method to charge
    - **plan_name**: Name of the subscription plan
    - **billing_interval**: Billing frequency (daily, weekly, monthly, quarterly, yearly)
    - **amount**: Amount to charge per billing period
    """
    service = SubscriptionService(db)
    event_pub = EventPublisher()

    try:
        result = await service.create_subscription(
            data=data,
            user_id=UUID(current_user["user_id"]),
        )

        await event_pub.publish_subscription_created(
            subscription_id=result.id,
            venue_id=result.venue_id,
            customer_id=result.customer_id,
            plan_name=result.plan_name,
            amount=result.amount,
            interval=result.billing_interval.value,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get subscription details",
)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific subscription."""
    service = SubscriptionService(db)

    try:
        return await service.get_subscription(subscription_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Update subscription",
)
async def update_subscription(
    subscription_id: UUID,
    data: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update subscription details like payment method or amount."""
    service = SubscriptionService(db)

    try:
        return await service.update_subscription(subscription_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel subscription",
)
async def cancel_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cancel an active subscription."""
    service = SubscriptionService(db)
    event_pub = EventPublisher()

    try:
        result = await service.cancel_subscription(
            subscription_id=subscription_id,
            user_id=UUID(current_user["user_id"]),
        )

        await event_pub.publish_subscription_cancelled(
            subscription_id=result.id,
            venue_id=result.venue_id,
            customer_id=result.customer_id,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{subscription_id}/pause",
    response_model=SubscriptionResponse,
    summary="Pause subscription",
)
async def pause_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Pause an active subscription temporarily."""
    service = SubscriptionService(db)
    event_pub = EventPublisher()

    try:
        result = await service.pause_subscription(
            subscription_id=subscription_id,
            user_id=UUID(current_user["user_id"]),
        )

        await event_pub.publish(
            EventType.SUBSCRIPTION_PAUSED,
            payload={
                "subscription_id": result.id,
                "customer_id": result.customer_id,
            },
            venue_id=result.venue_id,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{subscription_id}/resume",
    response_model=SubscriptionResponse,
    summary="Resume subscription",
)
async def resume_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Resume a paused subscription."""
    service = SubscriptionService(db)
    event_pub = EventPublisher()

    try:
        result = await service.resume_subscription(
            subscription_id=subscription_id,
            user_id=UUID(current_user["user_id"]),
        )

        await event_pub.publish(
            EventType.SUBSCRIPTION_RESUMED,
            payload={
                "subscription_id": result.id,
                "customer_id": result.customer_id,
            },
            venue_id=result.venue_id,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/",
    response_model=SubscriptionListResponse,
    summary="List subscriptions",
)
async def list_subscriptions(
    venue_id: UUID,
    customer_id: Optional[UUID] = None,
    status: Optional[SubscriptionStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """List subscriptions for a venue with filters and pagination."""
    service = SubscriptionService(db)

    params = PaginationParams(
        page=page,
        page_size=page_size,
    )

    return await service.list_subscriptions(
        venue_id=venue_id,
        customer_id=customer_id,
        status=status,
        params=params,
    )


@router.get(
    "/customer/{customer_id}",
    response_model=SubscriptionListResponse,
    summary="List customer subscriptions",
)
async def list_customer_subscriptions(
    customer_id: UUID,
    venue_id: Optional[UUID] = None,
    status: Optional[SubscriptionStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all subscriptions for a specific customer."""
    service = SubscriptionService(db)

    params = PaginationParams(
        page=page,
        page_size=page_size,
    )

    # If venue_id is provided, filter by venue
    if venue_id:
        return await service.list_subscriptions(
            venue_id=venue_id,
            customer_id=customer_id,
            status=status,
            params=params,
        )

    # Otherwise, get subscriptions across all venues (admin only)
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for cross-venue queries",
        )

    # For simplicity, return empty for now - would need different query
    return SubscriptionListResponse(
        subscriptions=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )
