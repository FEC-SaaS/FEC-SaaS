"""
=============================================================================
FILE: api/v1/family.py
PURPOSE: Family membership API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services import FamilyService
from app.services.event_publisher import event_publisher
from app.schemas.membership import (
    FamilyMembershipCreate,
    FamilyMembershipResponse,
    FamilyMemberRequest,
    FamilyMemberResponse,
)

router = APIRouter(prefix="/family", tags=["Family Memberships"])


# =============================================================================
# FAMILY MEMBERSHIPS
# =============================================================================


@router.post("", response_model=FamilyMembershipResponse, status_code=status.HTTP_201_CREATED)
async def create_family_membership(
    request: FamilyMembershipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new family membership."""
    service = FamilyService(db)

    try:
        family = await service.create_family_membership(
            primary_customer_id=current_user["customer_id"],
            request=request,
        )

        await event_publisher.publish(
            event_publisher.EVENT_FAMILY_CREATED,
            {
                "family_id": family.id,
                "primary_customer_id": current_user["customer_id"],
                "subscription_id": request.subscription_id,
            },
        )

        return family
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/my-family", response_model=FamilyMembershipResponse)
async def get_my_family(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the current customer's family membership."""
    service = FamilyService(db)
    family = await service.get_customer_family(current_user["customer_id"])
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not part of a family membership",
        )
    return family


@router.get("/{family_id}", response_model=FamilyMembershipResponse)
async def get_family_membership(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a family membership by ID."""
    service = FamilyService(db)
    family = await service.get_family_membership(family_id)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family membership not found",
        )

    # Verify user is a member
    members = await service.get_family_members(family_id)
    member_ids = [m.customer_id for m in members]
    if current_user["customer_id"] not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this family",
        )

    return family


@router.patch("/{family_id}", response_model=FamilyMembershipResponse)
async def update_family_membership(
    family_id: UUID,
    family_name: Optional[str] = None,
    max_members: Optional[int] = None,
    share_points: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update family membership settings."""
    service = FamilyService(db)
    family = await service.get_family_membership(family_id)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family membership not found",
        )

    # Only primary can update
    if family.primary_customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the primary member can update the family",
        )

    try:
        updated = await service.update_family_membership(
            family_id=family_id,
            family_name=family_name,
            max_members=max_members,
            share_points=share_points,
        )
        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# FAMILY MEMBERS
# =============================================================================


@router.post("/{family_id}/members", response_model=FamilyMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_family_member(
    family_id: UUID,
    request: FamilyMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a member to the family."""
    service = FamilyService(db)

    try:
        member = await service.add_family_member(
            family_id=family_id,
            request=request,
            added_by=current_user["customer_id"],
        )

        await event_publisher.publish(
            event_publisher.EVENT_FAMILY_MEMBER_ADDED,
            {
                "family_id": family_id,
                "member_id": member.id,
                "customer_id": request.customer_id,
                "added_by": current_user["customer_id"],
            },
        )

        return member
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{family_id}/members", response_model=List[FamilyMemberResponse])
async def list_family_members(
    family_id: UUID,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all members of a family."""
    service = FamilyService(db)
    family = await service.get_family_membership(family_id)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family membership not found",
        )

    members = await service.get_family_members(family_id, active_only=active_only)

    # Verify requester is a member
    member_ids = [m.customer_id for m in members]
    if current_user["customer_id"] not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    return members


@router.delete("/{family_id}/members/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_family_member(
    family_id: UUID,
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a member from the family."""
    service = FamilyService(db)

    try:
        success = await service.remove_family_member(
            family_id=family_id,
            customer_id=customer_id,
            removed_by=current_user["customer_id"],
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )

        await event_publisher.publish(
            event_publisher.EVENT_FAMILY_MEMBER_REMOVED,
            {
                "family_id": family_id,
                "customer_id": customer_id,
                "removed_by": current_user["customer_id"],
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{family_id}/transfer-primary", response_model=FamilyMembershipResponse)
async def transfer_primary_membership(
    family_id: UUID,
    new_primary_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Transfer primary membership to another family member."""
    service = FamilyService(db)

    try:
        family = await service.transfer_primary(
            family_id=family_id,
            new_primary_id=new_primary_id,
            current_primary_id=current_user["customer_id"],
        )
        return family
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# SHARED POINTS POOL
# =============================================================================


@router.get("/{family_id}/points-pool")
async def get_family_points_pool(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the family's shared points pool balance."""
    service = FamilyService(db)

    # Verify membership
    family = await service.get_family_membership(family_id)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family membership not found",
        )

    members = await service.get_family_members(family_id)
    member_ids = [m.customer_id for m in members]
    if current_user["customer_id"] not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    try:
        pool_info = await service.get_pool_balance(family_id)
        return pool_info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{family_id}/points-pool/contribute")
async def contribute_to_pool(
    family_id: UUID,
    points: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Contribute points to the family shared pool."""
    service = FamilyService(db)

    try:
        result = await service.contribute_to_pool(
            family_id=family_id,
            customer_id=current_user["customer_id"],
            points=points,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{family_id}/points-pool/use")
async def use_from_pool(
    family_id: UUID,
    points: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Use points from the family shared pool."""
    service = FamilyService(db)

    try:
        result = await service.use_from_pool(
            family_id=family_id,
            customer_id=current_user["customer_id"],
            points=points,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
