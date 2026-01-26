"""
=============================================================================
FILE: services/package_service.py
PURPOSE: Party package management business logic
=============================================================================
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.party import PartyPackage, PartyPackageAddon, PartyAddon
from app.schemas.party import (
    PartyPackageCreate,
    PartyPackageUpdate,
    PaginationParams,
)

logger = structlog.get_logger()


class PackageService:
    """Service for party package management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_package(self, package_data: PartyPackageCreate) -> PartyPackage:
        """
        Create a new party package.

        Args:
            package_data: Package creation data

        Returns:
            Created package instance
        """
        package = PartyPackage(
            venue_id=package_data.venue_id,
            package_name=package_data.package_name,
            package_type=package_data.package_type,
            description=package_data.description,
            min_guests=package_data.min_guests,
            max_guests=package_data.max_guests,
            base_price=package_data.base_price,
            price_per_additional_guest=package_data.price_per_additional_guest,
            deposit_percentage=package_data.deposit_percentage,
            duration_minutes=package_data.duration_minutes,
            includes_food=package_data.includes_food,
            includes_drinks=package_data.includes_drinks,
            includes_cake=package_data.includes_cake,
            includes_decorations=package_data.includes_decorations,
            includes_invitations=package_data.includes_invitations,
            included_activities=package_data.included_activities or {},
            display_order=package_data.display_order,
            is_featured=package_data.is_featured,
            image_url=package_data.image_url,
            is_active=True,
        )

        self.db.add(package)
        await self.db.flush()

        # Add default addons if provided
        if package_data.default_addon_ids:
            for addon_id in package_data.default_addon_ids:
                package_addon = PartyPackageAddon(
                    package_id=package.id,
                    addon_id=addon_id,
                    quantity=1,
                    is_included_free=True,
                )
                self.db.add(package_addon)

        await self.db.flush()
        await self.db.refresh(package)

        logger.info(
            "package_created",
            package_id=str(package.id),
            venue_id=str(package.venue_id),
            name=package.package_name,
        )

        return package

    async def get_package(self, package_id: UUID) -> Optional[PartyPackage]:
        """Get package by ID with default addons."""
        result = await self.db.execute(
            select(PartyPackage)
            .options(selectinload(PartyPackage.default_addons))
            .where(PartyPackage.id == package_id)
        )
        return result.scalar_one_or_none()

    async def list_packages(
        self,
        venue_id: UUID,
        pagination: PaginationParams,
        package_type: Optional[str] = None,
        is_active: Optional[bool] = True,
        is_featured: Optional[bool] = None,
    ) -> Tuple[List[PartyPackage], int]:
        """
        List packages for a venue with filtering and pagination.

        Returns:
            Tuple of (packages list, total count)
        """
        query = select(PartyPackage).where(PartyPackage.venue_id == venue_id)

        if is_active is not None:
            query = query.where(PartyPackage.is_active == is_active)

        if package_type:
            query = query.where(PartyPackage.package_type == package_type)

        if is_featured is not None:
            query = query.where(PartyPackage.is_featured == is_featured)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(PartyPackage, pagination.sort_by, PartyPackage.display_order)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        packages = list(result.scalars().all())

        return packages, total

    async def update_package(
        self,
        package_id: UUID,
        update_data: PartyPackageUpdate,
    ) -> Optional[PartyPackage]:
        """Update package information."""
        package = await self.get_package(package_id)
        if not package:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(package, field, value)

        package.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(package)

        logger.info(
            "package_updated",
            package_id=str(package_id),
            fields_updated=list(update_dict.keys()),
        )

        return package

    async def delete_package(self, package_id: UUID, hard_delete: bool = False) -> bool:
        """Delete a package (soft delete by default)."""
        package = await self.get_package(package_id)
        if not package:
            return False

        if hard_delete:
            await self.db.delete(package)
        else:
            package.is_active = False
            package.updated_at = datetime.utcnow()

        await self.db.flush()

        logger.info(
            "package_deleted",
            package_id=str(package_id),
            hard_delete=hard_delete,
        )

        return True

    async def add_default_addon(
        self,
        package_id: UUID,
        addon_id: UUID,
        quantity: int = 1,
        is_included_free: bool = True,
        discount_percentage: float = 0.0,
    ) -> Optional[PartyPackageAddon]:
        """Add a default addon to a package."""
        package = await self.get_package(package_id)
        if not package:
            return None

        # Check addon exists
        addon_result = await self.db.execute(
            select(PartyAddon).where(PartyAddon.id == addon_id)
        )
        addon = addon_result.scalar_one_or_none()
        if not addon:
            return None

        package_addon = PartyPackageAddon(
            package_id=package_id,
            addon_id=addon_id,
            quantity=quantity,
            is_included_free=is_included_free,
            discount_percentage=discount_percentage,
        )

        self.db.add(package_addon)
        await self.db.flush()
        await self.db.refresh(package_addon)

        return package_addon

    async def remove_default_addon(
        self,
        package_id: UUID,
        addon_id: UUID,
    ) -> bool:
        """Remove a default addon from a package."""
        result = await self.db.execute(
            select(PartyPackageAddon).where(
                and_(
                    PartyPackageAddon.package_id == package_id,
                    PartyPackageAddon.addon_id == addon_id,
                )
            )
        )
        package_addon = result.scalar_one_or_none()

        if not package_addon:
            return False

        await self.db.delete(package_addon)
        await self.db.flush()

        return True

    async def get_venue_package_count(self, venue_id: UUID) -> int:
        """Get count of packages for a venue."""
        result = await self.db.execute(
            select(func.count())
            .select_from(PartyPackage)
            .where(
                and_(
                    PartyPackage.venue_id == venue_id,
                    PartyPackage.is_active == True,
                )
            )
        )
        return result.scalar() or 0
