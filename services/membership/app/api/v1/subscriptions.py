"""
=============================================================================
FILE: api/v1/subscriptions.py
PURPOSE: Subscription management API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.services import SubscriptionService
from app.services.event_publisher import event_publisher
from app.schemas.membership import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanResponse,
    SubscribeRequest,
    SubscriptionResponse,
    SubscriptionPauseRequest,
    SubscriptionCancelRequest,
    SubscriptionUpgradeRequest,
    UsageLimitResponse,
    UsageLimitCreate,
    UsageRecordRequest,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# =============================================================================
# SUBSCRIPTION PLANS
# =============================================================================


@router.post("/plans", response_model=SubscriptionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    venue_id: UUID,
    plan_data: SubscriptionPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new subscription plan for a venue."""
    await require_venue_access(current_user, venue_id, "admin")
    service = SubscriptionService(db)
    plan = await service.create_plan(venue_id, plan_data)
    return plan


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def list_subscription_plans(
    venue_id: UUID,
    tier_id: Optional[UUID] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List subscription plans for a venue."""
    service = SubscriptionService(db)
    plans = await service.list_plans(
        venue_id=venue_id,
        tier_id=tier_id,
        active_only=active_only,
    )
    return plans


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific subscription plan."""
    service = SubscriptionService(db)
    plan = await service.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )
    return plan


@router.patch("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_subscription_plan(
    plan_id: UUID,
    plan_data: SubscriptionPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a subscription plan."""
    service = SubscriptionService(db)
    plan = await service.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )
    await require_venue_access(current_user, plan.venue_id, "admin")
    updated_plan = await service.update_plan(plan_id, plan_data)
    return updated_plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_subscription_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deactivate a subscription plan."""
    service = SubscriptionService(db)
    plan = await service.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )
    await require_venue_access(current_user, plan.venue_id, "admin")
    await service.deactivate_plan(plan_id)


# =============================================================================
# SUBSCRIPTIONS
# =============================================================================


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    request: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Subscribe a customer to a plan."""
    service = SubscriptionService(db)

    try:
        subscription = await service.subscribe(
            customer_id=current_user["customer_id"],
            request=request,
            payment_method_id=request.payment_method_id,
        )

        # Publish event
        plan = await service.get_plan(subscription.plan_id)
        await event_publisher.publish_subscription_created(
            subscription_id=subscription.id,
            customer_id=subscription.customer_id,
            plan_id=subscription.plan_id,
            venue_id=plan.venue_id if plan else None,
            status=subscription.status.value,
        )

        return subscription
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=List[SubscriptionResponse])
async def list_customer_subscriptions(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List subscriptions for the current customer."""
    service = SubscriptionService(db)
    subscriptions = await service.get_customer_subscriptions(
        customer_id=current_user["customer_id"],
        active_only=active_only,
    )
    return subscriptions


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific subscription."""
    service = SubscriptionService(db)
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    # Verify ownership
    if subscription.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this subscription",
        )
    return subscription


@router.post("/{subscription_id}/pause")
async def pause_subscription(
    subscription_id: UUID,
    request: SubscriptionPauseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Pause a subscription."""
    service = SubscriptionService(db)
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    if subscription.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    try:
        pause = await service.pause_subscription(subscription_id, request)

        await event_publisher.publish_subscription_paused(
            subscription_id=subscription_id,
            customer_id=subscription.customer_id,
            pause_reason=request.reason,
            scheduled_resume=request.resume_date,
        )

        return {"status": "paused", "scheduled_resume": pause.scheduled_resume}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{subscription_id}/resume", response_model=SubscriptionResponse)
async def resume_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Resume a paused subscription."""
    service = SubscriptionService(db)
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    if subscription.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    try:
        updated = await service.resume_subscription(subscription_id)

        await event_publisher.publish_subscription_resumed(
            subscription_id=subscription_id,
            customer_id=subscription.customer_id,
        )

        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: UUID,
    request: SubscriptionCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cancel a subscription."""
    service = SubscriptionService(db)
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    if subscription.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    updated = await service.cancel_subscription(subscription_id, request)

    await event_publisher.publish_subscription_cancelled(
        subscription_id=subscription_id,
        customer_id=subscription.customer_id,
        cancellation_reason=request.reason,
        immediate=request.immediate,
    )

    return updated


@router.post("/{subscription_id}/change-plan", response_model=SubscriptionResponse)
async def change_subscription_plan(
    subscription_id: UUID,
    request: SubscriptionUpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upgrade or downgrade a subscription to a different plan."""
    service = SubscriptionService(db)
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    if subscription.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    try:
        old_plan_id = subscription.plan_id
        updated = await service.upgrade_downgrade(subscription_id, request)

        await event_publisher.publish_subscription_upgraded(
            subscription_id=subscription_id,
            customer_id=subscription.customer_id,
            old_plan_id=old_plan_id,
            new_plan_id=request.new_plan_id,
        )

        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# USAGE TRACKING
# =============================================================================


@router.post("/plans/{plan_id}/usage-limits", response_model=UsageLimitResponse, status_code=status.HTTP_201_CREATED)
async def create_usage_limit(
    plan_id: UUID,
    limit_data: UsageLimitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a usage limit for a plan."""
    service = SubscriptionService(db)
    plan = await service.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    await require_venue_access(current_user, plan.venue_id, "admin")

    limit = await service.create_usage_limit(
        plan_id=plan_id,
        usage_type=limit_data.usage_type,
        limit_value=limit_data.limit_value,
        reset_period=limit_data.reset_period,
    )
    return limit


@router.get("/plans/{plan_id}/usage-limits", response_model=List[UsageLimitResponse])
async def get_usage_limits(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get usage limits for a plan."""
    service = SubscriptionService(db)
    limits = await service.get_usage_limits(plan_id)
    return limits


@router.post("/{subscription_id}/track-usage")
async def track_subscription_usage(
    subscription_id: UUID,
    usage_type: str,
    quantity: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Track usage for a subscription."""
    service = SubscriptionService(db)
    subscription = await service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    try:
        result = await service.track_usage(subscription_id, usage_type, quantity)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
