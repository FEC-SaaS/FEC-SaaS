"""
=============================================================================
FILE: api/v1/rewards.py
PURPOSE: Rewards catalog and redemption API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.services import RewardsService
from app.services.event_publisher import event_publisher
from app.models import RewardType, RedemptionStatus
from app.schemas.membership import (
    RewardCreate,
    RewardUpdate,
    RewardResponse,
    RedeemRewardRequest,
    RedemptionResponse,
)

router = APIRouter(prefix="/rewards", tags=["Rewards"])


# =============================================================================
# REWARDS CATALOG
# =============================================================================


@router.post("/catalog", response_model=RewardResponse, status_code=status.HTTP_201_CREATED)
async def create_reward(
    venue_id: UUID,
    reward_data: RewardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new reward in the catalog."""
    await require_venue_access(current_user, venue_id, "admin")
    service = RewardsService(db)
    reward = await service.create_reward(venue_id, reward_data)
    return reward


@router.get("/catalog", response_model=List[RewardResponse])
async def list_rewards(
    venue_id: UUID,
    reward_type: Optional[RewardType] = None,
    tier_id: Optional[UUID] = None,
    active_only: bool = True,
    available_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List rewards in the catalog."""
    service = RewardsService(db)
    rewards = await service.list_rewards(
        venue_id=venue_id,
        reward_type=reward_type,
        tier_id=tier_id,
        active_only=active_only,
        available_only=available_only,
    )
    return rewards


@router.get("/catalog/{reward_id}", response_model=RewardResponse)
async def get_reward(
    reward_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific reward."""
    service = RewardsService(db)
    reward = await service.get_reward(reward_id)
    if not reward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reward not found",
        )
    return reward


@router.patch("/catalog/{reward_id}", response_model=RewardResponse)
async def update_reward(
    reward_id: UUID,
    reward_data: RewardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a reward."""
    service = RewardsService(db)
    reward = await service.get_reward(reward_id)
    if not reward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reward not found",
        )
    await require_venue_access(current_user, reward.venue_id, "admin")
    updated = await service.update_reward(reward_id, reward_data)
    return updated


@router.delete("/catalog/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_reward(
    reward_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deactivate a reward."""
    service = RewardsService(db)
    reward = await service.get_reward(reward_id)
    if not reward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reward not found",
        )
    await require_venue_access(current_user, reward.venue_id, "admin")
    await service.deactivate_reward(reward_id)


@router.get("/available")
async def get_available_rewards_for_me(
    venue_id: UUID,
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get rewards available for the current customer."""
    service = RewardsService(db)
    rewards = await service.get_available_rewards_for_customer(
        venue_id=venue_id,
        customer_id=current_user["customer_id"],
        account_id=account_id,
    )
    return rewards


# =============================================================================
# REDEMPTIONS
# =============================================================================


@router.post("/redeem", response_model=RedemptionResponse, status_code=status.HTTP_201_CREATED)
async def redeem_reward(
    account_id: UUID,
    request: RedeemRewardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Redeem a reward."""
    service = RewardsService(db)

    try:
        redemption = await service.redeem_reward(
            customer_id=current_user["customer_id"],
            account_id=account_id,
            request=request,
        )

        # Publish event
        reward = await service.get_reward(request.reward_id)
        await event_publisher.publish_reward_redeemed(
            redemption_id=redemption.id,
            customer_id=current_user["customer_id"],
            reward_id=request.reward_id,
            reward_name=reward.name if reward else "Unknown",
            points_spent=redemption.points_spent,
        )

        return redemption
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/redemptions", response_model=List[RedemptionResponse])
async def list_my_redemptions(
    status: Optional[RedemptionStatus] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List redemptions for the current customer."""
    service = RewardsService(db)
    redemptions = await service.get_customer_redemptions(
        customer_id=current_user["customer_id"],
        status=status,
        limit=limit,
        offset=offset,
    )
    return redemptions


@router.get("/redemptions/{redemption_id}", response_model=RedemptionResponse)
async def get_redemption(
    redemption_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific redemption."""
    service = RewardsService(db)
    redemption = await service.get_redemption(redemption_id)
    if not redemption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redemption not found",
        )
    if redemption.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this redemption",
        )
    return redemption


@router.get("/redemptions/code/{redemption_code}", response_model=RedemptionResponse)
async def get_redemption_by_code(
    redemption_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a redemption by its code (for staff verification)."""
    service = RewardsService(db)
    redemption = await service.get_redemption_by_code(redemption_code)
    if not redemption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redemption not found",
        )
    return redemption


@router.post("/redemptions/{redemption_id}/fulfill", response_model=RedemptionResponse)
async def fulfill_redemption(
    redemption_id: UUID,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a redemption as fulfilled (staff action)."""
    service = RewardsService(db)
    redemption = await service.get_redemption(redemption_id)
    if not redemption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redemption not found",
        )

    # Get venue from reward for permission check
    reward = await service.get_reward(redemption.reward_id)
    if reward:
        await require_venue_access(current_user, reward.venue_id, "staff")

    try:
        fulfilled = await service.fulfill_redemption(
            redemption_id=redemption_id,
            fulfilled_by=current_user.get("user_id"),
            notes=notes,
        )
        return fulfilled
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/redemptions/{redemption_id}/cancel", response_model=RedemptionResponse)
async def cancel_redemption(
    redemption_id: UUID,
    reason: Optional[str] = None,
    refund_points: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cancel a redemption."""
    service = RewardsService(db)
    redemption = await service.get_redemption(redemption_id)
    if not redemption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redemption not found",
        )

    # Allow customer or staff to cancel
    if redemption.customer_id != current_user["customer_id"]:
        reward = await service.get_reward(redemption.reward_id)
        if reward:
            await require_venue_access(current_user, reward.venue_id, "staff")

    try:
        cancelled = await service.cancel_redemption(
            redemption_id=redemption_id,
            reason=reason,
            refund_points=refund_points,
        )
        return cancelled
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
