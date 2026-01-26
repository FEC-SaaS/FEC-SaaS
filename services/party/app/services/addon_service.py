"""
=============================================================================
FILE: services/addon_service.py
PURPOSE: Party addon management business logic
=============================================================================
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.party import PartyAddon, AddonType
from app.schemas.party import (
    PartyAddonCreate,
    PartyAddonUpdate,
    PaginationParams,
)

logger = structlog.get_logger()


class AddonService:
    """Service for party addon management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_addon(self, addon_data: PartyAddonCreate) -> PartyAddon:
        """
        Create a new party addon.

        Args:
            addon_data: Addon creation data

        Returns:
            Created addon instance
        """
        addon = PartyAddon(
            venue_id=addon_data.venue_id,
            addon_name=addon_data.addon_name,
            addon_type=addon_data.addon_type,
            description=addon_data.description,
            price=addon_data.price,
            price_type=addon_data.price_type,
            min_quantity=addon_data.min_quantity,
            max_quantity=addon_data.max_quantity,
            requires_advance_notice_hours=addon_data.requires_advance_notice_hours,
            display_order=addon_data.display_order,
            image_url=addon_data.image_url,
            upsell_priority=addon_data.upsell_priority,
            upsell_message=addon_data.upsell_message,
            is_active=True,
        )

        self.db.add(addon)
        await self.db.flush()
        await self.db.refresh(addon)

        logger.info(
            "addon_created",
            addon_id=str(addon.id),
            venue_id=str(addon.venue_id),
            name=addon.addon_name,
        )

        return addon

    async def get_addon(self, addon_id: UUID) -> Optional[PartyAddon]:
        """Get addon by ID."""
        result = await self.db.execute(
            select(PartyAddon).where(PartyAddon.id == addon_id)
        )
        return result.scalar_one_or_none()

    async def list_addons(
        self,
        venue_id: UUID,
        pagination: PaginationParams,
        addon_type: Optional[AddonType] = None,
        is_active: Optional[bool] = True,
    ) -> Tuple[List[PartyAddon], int]:
        """
        List addons for a venue with filtering and pagination.

        Returns:
            Tuple of (addons list, total count)
        """
        query = select(PartyAddon).where(PartyAddon.venue_id == venue_id)

        if is_active is not None:
            query = query.where(PartyAddon.is_active == is_active)

        if addon_type:
            query = query.where(PartyAddon.addon_type == addon_type)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(PartyAddon, pagination.sort_by, PartyAddon.display_order)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        addons = list(result.scalars().all())

        return addons, total

    async def update_addon(
        self,
        addon_id: UUID,
        update_data: PartyAddonUpdate,
    ) -> Optional[PartyAddon]:
        """Update addon information."""
        addon = await self.get_addon(addon_id)
        if not addon:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(addon, field, value)

        addon.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(addon)

        logger.info(
            "addon_updated",
            addon_id=str(addon_id),
            fields_updated=list(update_dict.keys()),
        )

        return addon

    async def delete_addon(self, addon_id: UUID, hard_delete: bool = False) -> bool:
        """Delete an addon (soft delete by default)."""
        addon = await self.get_addon(addon_id)
        if not addon:
            return False

        if hard_delete:
            await self.db.delete(addon)
        else:
            addon.is_active = False
            addon.updated_at = datetime.utcnow()

        await self.db.flush()

        logger.info(
            "addon_deleted",
            addon_id=str(addon_id),
            hard_delete=hard_delete,
        )

        return True

    async def get_upsell_suggestions(
        self,
        venue_id: UUID,
        package_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[PartyAddon]:
        """
        Get upsell addon suggestions for AI-powered recommendations.

        Returns addons sorted by upsell priority.
        """
        query = (
            select(PartyAddon)
            .where(
                and_(
                    PartyAddon.venue_id == venue_id,
                    PartyAddon.is_active == True,
                    PartyAddon.upsell_priority > 0,
                )
            )
            .order_by(PartyAddon.upsell_priority.desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_venue_addon_count(self, venue_id: UUID) -> int:
        """Get count of addons for a venue."""
        result = await self.db.execute(
            select(func.count())
            .select_from(PartyAddon)
            .where(
                and_(
                    PartyAddon.venue_id == venue_id,
                    PartyAddon.is_active == True,
                )
            )
        )
        return result.scalar() or 0
