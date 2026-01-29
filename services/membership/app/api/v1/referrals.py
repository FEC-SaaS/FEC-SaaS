"""
=============================================================================
FILE: api/v1/referrals.py
PURPOSE: Referral program API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.services import ReferralService
from app.services.event_publisher import event_publisher
from app.models import ReferralStatus
from app.schemas.membership import (
    ReferralResponse,
    ReferralStatsResponse,
)

router = APIRouter(prefix="/referrals", tags=["Referrals"])


# =============================================================================
# REFERRAL CODES
# =============================================================================


@router.post("/code", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
async def create_referral_code(
    venue_id: UUID,
    referrer_reward_points: Optional[int] = None,
    referred_reward_points: Optional[int] = None,
    expires_in_days: int = 90,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create or get a referral code for the current customer."""
    service = ReferralService(db)

    referral = await service.create_referral_code(
        referrer_id=current_user["customer_id"],
        venue_id=venue_id,
        referrer_reward_points=referrer_reward_points,
        referred_reward_points=referred_reward_points,
        expires_in_days=expires_in_days,
    )
    return referral


@router.get("/my-code")
async def get_my_referral_code(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the current customer's active referral code."""
    service = ReferralService(db)

    referral = await service.get_active_referral_code(
        referrer_id=current_user["customer_id"],
        venue_id=venue_id,
    )
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active referral code found. Create one first.",
        )
    return {
        "referral_code": referral.referral_code,
        "referrer_reward_points": referral.referrer_reward_points,
        "referred_reward_points": referral.referred_reward_points,
        "expires_at": referral.expires_at,
    }


@router.get("/my-referrals", response_model=List[ReferralResponse])
async def list_my_referrals(
    status: Optional[ReferralStatus] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all referrals made by the current customer."""
    service = ReferralService(db)

    referrals = await service.get_customer_referrals(
        referrer_id=current_user["customer_id"],
        status=status,
        limit=limit,
        offset=offset,
    )
    return referrals


@router.get("/my-stats", response_model=ReferralStatsResponse)
async def get_my_referral_stats(
    venue_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get referral statistics for the current customer."""
    service = ReferralService(db)

    stats = await service.get_referral_stats(
        referrer_id=current_user["customer_id"],
        venue_id=venue_id,
    )
    return stats


# =============================================================================
# REFERRAL REDEMPTION
# =============================================================================


@router.post("/use")
async def use_referral_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Use a referral code (for new customers signing up)."""
    service = ReferralService(db)

    try:
        result = await service.use_referral_code(
            code=code,
            referred_id=current_user["customer_id"],
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/validate/{code}")
async def validate_referral_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Validate a referral code without using it."""
    service = ReferralService(db)

    referral = await service.get_by_code(code)
    if not referral:
        return {"valid": False, "reason": "Invalid referral code"}

    if referral.status != ReferralStatus.ACTIVE:
        return {"valid": False, "reason": "Referral code is not active"}

    if referral.expires_at and referral.expires_at < __import__("datetime").datetime.utcnow():
        return {"valid": False, "reason": "Referral code has expired"}

    return {
        "valid": True,
        "referrer_id": referral.referrer_id,
        "referred_reward_points": referral.referred_reward_points,
    }


@router.post("/{referral_id}/complete")
async def complete_referral(
    referral_id: UUID,
    qualifying_action: str = "subscription",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Complete a referral and issue rewards (internal/admin endpoint)."""
    service = ReferralService(db)

    try:
        result = await service.complete_referral(
            referral_id=referral_id,
            qualifying_action=qualifying_action,
        )

        # Publish event
        referral = await service.get_referral(referral_id)
        if referral:
            await event_publisher.publish_referral_completed(
                referral_id=referral_id,
                referrer_id=referral.referrer_id,
                referred_id=referral.referred_id,
                referrer_reward_points=referral.referrer_reward_points,
                referred_reward_points=referral.referred_reward_points,
            )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# VENUE ANALYTICS
# =============================================================================


@router.get("/venue/{venue_id}/stats")
async def get_venue_referral_stats(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get referral statistics for a venue."""
    await require_venue_access(current_user, venue_id, "staff")

    service = ReferralService(db)
    stats = await service.get_venue_referral_stats(venue_id)
    return stats


@router.get("/venue/{venue_id}/leaderboard")
async def get_referral_leaderboard(
    venue_id: UUID,
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get referral leaderboard for a venue."""
    service = ReferralService(db)
    leaderboard = await service.get_leaderboard(venue_id, limit)
    return leaderboard
