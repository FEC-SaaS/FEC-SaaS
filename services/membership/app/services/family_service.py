"""
=============================================================================
FILE: services/family_service.py
PURPOSE: Family membership management service
=============================================================================
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    FamilyMembership,
    FamilyMembershipMember,
    CustomerSubscription,
    SubscriptionPlan,
    RelationshipType,
)
from app.schemas.membership import (
    FamilyMembershipCreate,
    FamilyMemberRequest,
)


class FamilyService:
    """Service for managing family memberships."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # FAMILY MEMBERSHIPS
    # =========================================================================

    async def create_family_membership(
        self,
        primary_customer_id: UUID,
        request: FamilyMembershipCreate,
    ) -> FamilyMembership:
        """Create a new family membership plan."""
        # Validate subscription exists and is active
        result = await self.db.execute(
            select(CustomerSubscription)
            .where(CustomerSubscription.id == request.subscription_id)
            .options(selectinload(CustomerSubscription.plan))
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError("Subscription not found")

        # Create family membership
        family = FamilyMembership(
            subscription_id=request.subscription_id,
            primary_customer_id=primary_customer_id,
            family_name=request.family_name,
            max_members=request.max_members,
            share_points=request.share_points,
            shared_points_pool=0,
        )
        self.db.add(family)
        await self.db.commit()
        await self.db.refresh(family)

        # Add primary member automatically
        primary_member = FamilyMembershipMember(
            family_id=family.id,
            customer_id=primary_customer_id,
            relationship=RelationshipType.PRIMARY,
            is_active=True,
            joined_at=datetime.utcnow(),
        )
        self.db.add(primary_member)
        await self.db.commit()

        return family

    async def get_family_membership(
        self, family_id: UUID
    ) -> Optional[FamilyMembership]:
        """Get a family membership by ID."""
        result = await self.db.execute(
            select(FamilyMembership)
            .where(FamilyMembership.id == family_id)
            .options(
                selectinload(FamilyMembership.members),
                selectinload(FamilyMembership.subscription),
            )
        )
        return result.scalar_one_or_none()

    async def get_customer_family(
        self, customer_id: UUID
    ) -> Optional[FamilyMembership]:
        """Get family membership for a customer (as primary or member)."""
        # Check if primary
        result = await self.db.execute(
            select(FamilyMembership)
            .where(FamilyMembership.primary_customer_id == customer_id)
            .options(selectinload(FamilyMembership.members))
        )
        family = result.scalar_one_or_none()
        if family:
            return family

        # Check if member
        result = await self.db.execute(
            select(FamilyMembershipMember)
            .where(
                and_(
                    FamilyMembershipMember.customer_id == customer_id,
                    FamilyMembershipMember.is_active == True,
                )
            )
        )
        member = result.scalar_one_or_none()
        if member:
            return await self.get_family_membership(member.family_id)

        return None

    async def update_family_membership(
        self,
        family_id: UUID,
        family_name: Optional[str] = None,
        max_members: Optional[int] = None,
        share_points: Optional[bool] = None,
    ) -> Optional[FamilyMembership]:
        """Update family membership settings."""
        family = await self.get_family_membership(family_id)
        if not family:
            return None

        if family_name is not None:
            family.family_name = family_name
        if max_members is not None:
            # Check current member count
            current_count = len([m for m in family.members if m.is_active])
            if max_members < current_count:
                raise ValueError(
                    f"Cannot reduce max members below current count ({current_count})"
                )
            family.max_members = max_members
        if share_points is not None:
            family.share_points = share_points

        await self.db.commit()
        await self.db.refresh(family)
        return family

    # =========================================================================
    # FAMILY MEMBERS
    # =========================================================================

    async def add_family_member(
        self,
        family_id: UUID,
        request: FamilyMemberRequest,
        added_by: UUID,
    ) -> FamilyMembershipMember:
        """Add a member to a family membership."""
        family = await self.get_family_membership(family_id)
        if not family:
            raise ValueError("Family membership not found")

        # Verify requester is primary
        if family.primary_customer_id != added_by:
            raise ValueError("Only the primary member can add family members")

        # Check member limit
        active_members = len([m for m in family.members if m.is_active])
        if active_members >= family.max_members:
            raise ValueError("Family membership has reached maximum members")

        # Check if customer is already a member
        existing = await self._get_member(family_id, request.customer_id)
        if existing and existing.is_active:
            raise ValueError("Customer is already a family member")

        # Reactivate or create member
        if existing:
            existing.is_active = True
            existing.member_relationship = request.relationship
            existing.joined_at = datetime.utcnow()
            member = existing
        else:
            member = FamilyMembershipMember(
                family_id=family_id,
                customer_id=request.customer_id,
                member_relationship=request.relationship,
                is_active=True,
                joined_at=datetime.utcnow(),
            )
            self.db.add(member)

        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_family_member(
        self,
        family_id: UUID,
        customer_id: UUID,
        removed_by: UUID,
    ) -> bool:
        """Remove a member from a family membership."""
        family = await self.get_family_membership(family_id)
        if not family:
            return False

        # Verify requester has permission
        if family.primary_customer_id != removed_by and customer_id != removed_by:
            raise ValueError("Not authorized to remove this member")

        # Cannot remove primary member
        if customer_id == family.primary_customer_id:
            raise ValueError("Cannot remove primary member. Transfer primary status first.")

        member = await self._get_member(family_id, customer_id)
        if not member or not member.is_active:
            return False

        member.is_active = False
        member.left_at = datetime.utcnow()

        await self.db.commit()
        return True

    async def transfer_primary(
        self,
        family_id: UUID,
        new_primary_id: UUID,
        current_primary_id: UUID,
    ) -> FamilyMembership:
        """Transfer primary membership to another family member."""
        family = await self.get_family_membership(family_id)
        if not family:
            raise ValueError("Family membership not found")

        if family.primary_customer_id != current_primary_id:
            raise ValueError("Only the current primary can transfer ownership")

        # Verify new primary is an active member
        new_primary_member = await self._get_member(family_id, new_primary_id)
        if not new_primary_member or not new_primary_member.is_active:
            raise ValueError("New primary must be an active family member")

        # Update relationships
        old_primary_member = await self._get_member(family_id, current_primary_id)
        if old_primary_member:
            old_primary_member.member_relationship = RelationshipType.SPOUSE  # Default

        new_primary_member.member_relationship = RelationshipType.PRIMARY

        # Update family
        family.primary_customer_id = new_primary_id

        await self.db.commit()
        await self.db.refresh(family)
        return family

    async def get_family_members(
        self, family_id: UUID, active_only: bool = True
    ) -> List[FamilyMembershipMember]:
        """Get all members of a family."""
        query = select(FamilyMembershipMember).where(
            FamilyMembershipMember.family_id == family_id
        )
        if active_only:
            query = query.where(FamilyMembershipMember.is_active == True)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # SHARED POINTS
    # =========================================================================

    async def contribute_to_pool(
        self,
        family_id: UUID,
        customer_id: UUID,
        points: int,
    ) -> Dict[str, Any]:
        """Contribute points to the family shared pool."""
        family = await self.get_family_membership(family_id)
        if not family:
            raise ValueError("Family membership not found")

        if not family.share_points:
            raise ValueError("Points sharing is not enabled for this family")

        # Verify customer is a member
        member = await self._get_member(family_id, customer_id)
        if not member or not member.is_active:
            raise ValueError("Not a member of this family")

        # This would integrate with loyalty service to deduct from individual
        # and add to shared pool
        family.shared_points_pool += points

        await self.db.commit()

        return {
            "contributed": points,
            "new_pool_balance": family.shared_points_pool,
        }

    async def use_from_pool(
        self,
        family_id: UUID,
        customer_id: UUID,
        points: int,
    ) -> Dict[str, Any]:
        """Use points from the family shared pool."""
        family = await self.get_family_membership(family_id)
        if not family:
            raise ValueError("Family membership not found")

        if not family.share_points:
            raise ValueError("Points sharing is not enabled for this family")

        # Verify customer is a member
        member = await self._get_member(family_id, customer_id)
        if not member or not member.is_active:
            raise ValueError("Not a member of this family")

        if family.shared_points_pool < points:
            raise ValueError("Insufficient points in family pool")

        family.shared_points_pool -= points

        await self.db.commit()

        return {
            "used": points,
            "remaining_pool_balance": family.shared_points_pool,
        }

    async def get_pool_balance(self, family_id: UUID) -> Dict[str, Any]:
        """Get the current family points pool balance."""
        family = await self.get_family_membership(family_id)
        if not family:
            raise ValueError("Family membership not found")

        return {
            "share_points_enabled": family.share_points,
            "pool_balance": family.shared_points_pool,
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _get_member(
        self, family_id: UUID, customer_id: UUID
    ) -> Optional[FamilyMembershipMember]:
        """Get a specific family member."""
        result = await self.db.execute(
            select(FamilyMembershipMember).where(
                and_(
                    FamilyMembershipMember.family_id == family_id,
                    FamilyMembershipMember.customer_id == customer_id,
                )
            )
        )
        return result.scalar_one_or_none()
