"""
=============================================================================
FILE: api/v1/tiers.py
PURPOSE: Membership tier management API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.models import MembershipTier
from app.schemas.membership import (
    MembershipTierCreate,
    MembershipTierUpdate,
    MembershipTierResponse,
)

router = APIRouter(prefix="/tiers", tags=["Membership Tiers"])


@router.post("", response_model=MembershipTierResponse, status_code=status.HTTP_201_CREATED)
async def create_tier(
    venue_id: UUID,
    tier_data: MembershipTierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new membership tier."""
    await require_venue_access(current_user, venue_id, "admin")

    tier = MembershipTier(
        venue_id=venue_id,
        name=tier_data.name,
        description=tier_data.description,
        level=tier_data.level,
        min_points=tier_data.min_points,
        min_spend=tier_data.min_spend,
        benefits=tier_data.benefits or {},
        color=tier_data.color,
        icon=tier_data.icon,
        is_active=True,
    )
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    return tier


@router.get("", response_model=List[MembershipTierResponse])
async def list_tiers(
    venue_id: UUID,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List membership tiers for a venue."""
    query = select(MembershipTier).where(MembershipTier.venue_id == venue_id)
    if active_only:
        query = query.where(MembershipTier.is_active == True)
    query = query.order_by(MembershipTier.level)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{tier_id}", response_model=MembershipTierResponse)
async def get_tier(
    tier_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific membership tier."""
    result = await db.execute(
        select(MembershipTier).where(MembershipTier.id == tier_id)
    )
    tier = result.scalar_one_or_none()
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership tier not found",
        )
    return tier


@router.patch("/{tier_id}", response_model=MembershipTierResponse)
async def update_tier(
    tier_id: UUID,
    tier_data: MembershipTierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a membership tier."""
    result = await db.execute(
        select(MembershipTier).where(MembershipTier.id == tier_id)
    )
    tier = result.scalar_one_or_none()
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership tier not found",
        )

    await require_venue_access(current_user, tier.venue_id, "admin")

    update_data = tier_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tier, field, value)

    await db.commit()
    await db.refresh(tier)
    return tier


@router.delete("/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tier(
    tier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deactivate a membership tier."""
    result = await db.execute(
        select(MembershipTier).where(MembershipTier.id == tier_id)
    )
    tier = result.scalar_one_or_none()
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership tier not found",
        )

    await require_venue_access(current_user, tier.venue_id, "admin")

    tier.is_active = False
    await db.commit()
