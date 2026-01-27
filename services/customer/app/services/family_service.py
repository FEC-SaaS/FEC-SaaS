"""
=============================================================================
FILE: services/family_service.py
PURPOSE: Family management business logic
=============================================================================
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.customer import (
    Customer,
    CustomerFamily,
    CustomerFamilyMember,
    RelationshipType,
)
from app.schemas.customer import FamilyCreate, FamilyUpdate, FamilyMemberCreate

logger = structlog.get_logger()


class FamilyService:
    """Service for family management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_family(self, family_data: FamilyCreate) -> CustomerFamily:
        """Create a new family."""
        family = CustomerFamily(
            venue_id=family_data.venue_id,
            family_name=family_data.family_name,
            primary_customer_id=family_data.primary_customer_id,
            notes=family_data.notes,
        )

        self.db.add(family)
        await self.db.flush()

        # Add primary customer as a member
        primary_member = CustomerFamilyMember(
            family_id=family.id,
            customer_id=family_data.primary_customer_id,
            relation_type=RelationshipType.PARENT,
        )
        self.db.add(primary_member)

        # Add additional members if provided
        if family_data.members:
            for member_data in family_data.members:
                if member_data.customer_id != family_data.primary_customer_id:
                    member = CustomerFamilyMember(
                        family_id=family.id,
                        customer_id=member_data.customer_id,
                        relation_type=member_data.relation_type,
                    )
                    self.db.add(member)

        await self.db.flush()
        await self.db.refresh(family)

        logger.info(
            "family_created",
            family_id=str(family.id),
            family_name=family.family_name,
        )

        return family

    async def get_family(self, family_id: UUID) -> Optional[CustomerFamily]:
        """Get family by ID with members."""
        result = await self.db.execute(
            select(CustomerFamily)
            .options(
                selectinload(CustomerFamily.members).selectinload(
                    CustomerFamilyMember.customer
                ),
                selectinload(CustomerFamily.primary_customer),
            )
            .where(CustomerFamily.id == family_id)
        )
        return result.scalar_one_or_none()

    async def list_families(
        self,
        venue_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CustomerFamily]:
        """List families for a venue."""
        result = await self.db.execute(
            select(CustomerFamily)
            .options(selectinload(CustomerFamily.members))
            .where(CustomerFamily.venue_id == venue_id)
            .order_by(CustomerFamily.family_name)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_family(
        self,
        family_id: UUID,
        update_data: FamilyUpdate,
    ) -> Optional[CustomerFamily]:
        """Update family information."""
        family = await self.get_family(family_id)
        if not family:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(family, field, value)

        family.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(family)

        return family

    async def delete_family(self, family_id: UUID) -> bool:
        """Delete a family."""
        family = await self.get_family(family_id)
        if not family:
            return False

        await self.db.delete(family)
        await self.db.flush()

        logger.info("family_deleted", family_id=str(family_id))
        return True

    async def add_family_member(
        self,
        family_id: UUID,
        member_data: FamilyMemberCreate,
    ) -> Optional[CustomerFamilyMember]:
        """Add a member to a family."""
        family = await self.get_family(family_id)
        if not family:
            return None

        # Check if customer exists
        customer_result = await self.db.execute(
            select(Customer).where(Customer.id == member_data.customer_id)
        )
        if not customer_result.scalar_one_or_none():
            return None

        # Check if already a member
        existing = await self.db.execute(
            select(CustomerFamilyMember).where(
                and_(
                    CustomerFamilyMember.family_id == family_id,
                    CustomerFamilyMember.customer_id == member_data.customer_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            return None

        member = CustomerFamilyMember(
            family_id=family_id,
            customer_id=member_data.customer_id,
            relation_type=member_data.relation_type,
        )

        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)

        return member

    async def remove_family_member(
        self,
        family_id: UUID,
        member_id: UUID,
    ) -> bool:
        """Remove a member from a family."""
        result = await self.db.execute(
            select(CustomerFamilyMember).where(
                and_(
                    CustomerFamilyMember.family_id == family_id,
                    CustomerFamilyMember.id == member_id,
                )
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            return False

        await self.db.delete(member)
        await self.db.flush()

        return True

    async def get_customer_families(
        self,
        customer_id: UUID,
    ) -> List[CustomerFamily]:
        """Get all families a customer belongs to."""
        result = await self.db.execute(
            select(CustomerFamily)
            .join(CustomerFamilyMember)
            .where(CustomerFamilyMember.customer_id == customer_id)
            .options(selectinload(CustomerFamily.members))
        )
        return list(result.scalars().all())
