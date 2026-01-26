"""
=============================================================================
FILE: services/venue_service.py
PURPOSE: Core venue management business logic
=============================================================================

Handles all venue CRUD operations, search, filtering, and coordination
with other services for venue lifecycle management.
"""

import re
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.venue import (
    Venue,
    VenueHours,
    VenueFeature,
    VenueStatus,
    SubscriptionTier,
    OnboardingStatus,
)
from app.schemas.venue import (
    VenueCreate,
    VenueUpdate,
    VenueFilters,
    PaginationParams,
)

logger = structlog.get_logger()


class VenueService:
    """Service for venue management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_venue(self, venue_data: VenueCreate) -> Venue:
        """
        Create a new venue.

        Args:
            venue_data: Venue creation data

        Returns:
            Created venue instance
        """
        # Generate slug if not provided
        slug = venue_data.slug or self._generate_slug(venue_data.name, venue_data.city)

        # Ensure slug is unique
        slug = await self._ensure_unique_slug(slug)

        # Create venue instance
        venue = Venue(
            name=venue_data.name,
            legal_name=venue_data.legal_name,
            description=venue_data.description,
            slug=slug,
            address_line1=venue_data.address_line1,
            address_line2=venue_data.address_line2,
            city=venue_data.city,
            state=venue_data.state,
            postal_code=venue_data.postal_code,
            country=venue_data.country,
            latitude=venue_data.latitude,
            longitude=venue_data.longitude,
            timezone=venue_data.timezone,
            phone=venue_data.phone,
            email=venue_data.email,
            website=venue_data.website,
            tax_id=venue_data.tax_id,
            subscription_tier=venue_data.subscription_tier,
            total_capacity=venue_data.total_capacity,
            square_footage=venue_data.square_footage,
            franchise_id=venue_data.franchise_id,
            is_flagship=venue_data.is_flagship,
            status=VenueStatus.PENDING,
            onboarding_status=OnboardingStatus.NOT_STARTED,
        )

        self.db.add(venue)
        await self.db.flush()

        # Add default hours if provided
        if venue_data.hours:
            for hours_data in venue_data.hours:
                hours = VenueHours(
                    venue_id=venue.id,
                    day_of_week=hours_data.day_of_week,
                    open_time=hours_data.open_time,
                    close_time=hours_data.close_time,
                    is_closed=hours_data.is_closed,
                    is_24_hours=hours_data.is_24_hours,
                )
                self.db.add(hours)

        # Enable default features if provided
        if venue_data.features:
            for feature_name in venue_data.features:
                feature = VenueFeature(
                    venue_id=venue.id,
                    feature_name=feature_name,
                    is_enabled=True,
                    enabled_at=datetime.utcnow(),
                )
                self.db.add(feature)

        await self.db.flush()
        await self.db.refresh(venue)

        logger.info(
            "venue_created",
            venue_id=str(venue.id),
            name=venue.name,
            slug=venue.slug,
        )

        return venue

    async def get_venue(self, venue_id: UUID) -> Optional[Venue]:
        """
        Get venue by ID with all related data.

        Args:
            venue_id: Venue UUID

        Returns:
            Venue instance or None
        """
        result = await self.db.execute(
            select(Venue)
            .options(
                selectinload(Venue.hours),
                selectinload(Venue.special_hours),
                selectinload(Venue.features),
                selectinload(Venue.ai_configs),
                selectinload(Venue.contacts),
                selectinload(Venue.images),
            )
            .where(
                Venue.id == venue_id,
                Venue.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_venue_by_slug(self, slug: str) -> Optional[Venue]:
        """Get venue by slug."""
        result = await self.db.execute(
            select(Venue)
            .options(
                selectinload(Venue.hours),
                selectinload(Venue.features),
            )
            .where(
                Venue.slug == slug,
                Venue.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def list_venues(
        self,
        filters: VenueFilters,
        pagination: PaginationParams,
    ) -> Tuple[List[Venue], int]:
        """
        List venues with filtering and pagination.

        Args:
            filters: Filter parameters
            pagination: Pagination parameters

        Returns:
            Tuple of (venues list, total count)
        """
        # Base query
        query = select(Venue).where(Venue.is_deleted == False)

        # Apply filters
        if filters.status:
            query = query.where(Venue.status == filters.status)

        if filters.subscription_tier:
            query = query.where(Venue.subscription_tier == filters.subscription_tier)

        if filters.city:
            query = query.where(Venue.city.ilike(f"%{filters.city}%"))

        if filters.state:
            query = query.where(Venue.state.ilike(f"%{filters.state}%"))

        if filters.franchise_id:
            query = query.where(Venue.franchise_id == filters.franchise_id)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(
                or_(
                    Venue.name.ilike(search_term),
                    Venue.address_line1.ilike(search_term),
                    Venue.city.ilike(search_term),
                )
            )

        if filters.has_feature:
            # Join with features to filter
            query = query.join(VenueFeature).where(
                and_(
                    VenueFeature.feature_name == filters.has_feature,
                    VenueFeature.is_enabled == True,
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Venue, pagination.sort_by, Venue.created_at)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        # Execute query
        result = await self.db.execute(query)
        venues = list(result.scalars().all())

        return venues, total

    async def update_venue(
        self,
        venue_id: UUID,
        update_data: VenueUpdate,
    ) -> Optional[Venue]:
        """
        Update venue information.

        Args:
            venue_id: Venue UUID
            update_data: Fields to update

        Returns:
            Updated venue or None
        """
        venue = await self.get_venue(venue_id)
        if not venue:
            return None

        # Update only provided fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(venue, field, value)

        venue.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(venue)

        logger.info(
            "venue_updated",
            venue_id=str(venue_id),
            fields_updated=list(update_dict.keys()),
        )

        return venue

    async def delete_venue(self, venue_id: UUID, hard_delete: bool = False) -> bool:
        """
        Delete a venue (soft delete by default).

        Args:
            venue_id: Venue UUID
            hard_delete: If True, permanently delete

        Returns:
            True if deleted, False if not found
        """
        venue = await self.get_venue(venue_id)
        if not venue:
            return False

        if hard_delete:
            await self.db.delete(venue)
        else:
            venue.is_deleted = True
            venue.deleted_at = datetime.utcnow()
            venue.status = VenueStatus.CLOSED

        await self.db.flush()

        logger.info(
            "venue_deleted",
            venue_id=str(venue_id),
            hard_delete=hard_delete,
        )

        return True

    async def update_status(
        self,
        venue_id: UUID,
        new_status: VenueStatus,
    ) -> Optional[Venue]:
        """
        Update venue status.

        Args:
            venue_id: Venue UUID
            new_status: New status to set

        Returns:
            Updated venue or None
        """
        venue = await self.get_venue(venue_id)
        if not venue:
            return None

        old_status = venue.status
        venue.status = new_status
        venue.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(venue)

        logger.info(
            "venue_status_changed",
            venue_id=str(venue_id),
            old_status=old_status.value,
            new_status=new_status.value,
        )

        return venue

    # =========================================================================
    # Franchise Operations
    # =========================================================================

    async def list_franchise_venues(
        self,
        franchise_id: UUID,
    ) -> List[Venue]:
        """Get all venues for a franchise."""
        result = await self.db.execute(
            select(Venue)
            .where(
                Venue.franchise_id == franchise_id,
                Venue.is_deleted == False,
            )
            .order_by(Venue.name)
        )
        return list(result.scalars().all())

    async def bulk_create_venues(
        self,
        venues_data: List[VenueCreate],
        franchise_id: Optional[UUID] = None,
    ) -> List[Venue]:
        """
        Create multiple venues at once.

        Args:
            venues_data: List of venue creation data
            franchise_id: Optional franchise to assign all venues to

        Returns:
            List of created venues
        """
        created_venues = []

        for venue_data in venues_data:
            if franchise_id:
                venue_data.franchise_id = franchise_id

            venue = await self.create_venue(venue_data)
            created_venues.append(venue)

        logger.info(
            "bulk_venues_created",
            count=len(created_venues),
            franchise_id=str(franchise_id) if franchise_id else None,
        )

        return created_venues

    async def bulk_update_venues(
        self,
        venue_ids: List[UUID],
        update_data: VenueUpdate,
    ) -> int:
        """
        Update multiple venues at once.

        Args:
            venue_ids: List of venue UUIDs to update
            update_data: Fields to update

        Returns:
            Number of venues updated
        """
        updated_count = 0

        for venue_id in venue_ids:
            result = await self.update_venue(venue_id, update_data)
            if result:
                updated_count += 1

        logger.info(
            "bulk_venues_updated",
            count=updated_count,
            total_requested=len(venue_ids),
        )

        return updated_count

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _generate_slug(self, name: str, city: str) -> str:
        """Generate URL-friendly slug from venue name and city."""
        combined = f"{name}-{city}"
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", combined.lower())
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Limit length
        return slug[:100]

    async def _ensure_unique_slug(self, base_slug: str) -> str:
        """Ensure slug is unique by appending number if needed."""
        slug = base_slug
        counter = 1

        while True:
            result = await self.db.execute(
                select(func.count())
                .select_from(Venue)
                .where(Venue.slug == slug)
            )
            count = result.scalar() or 0

            if count == 0:
                return slug

            slug = f"{base_slug}-{counter}"
            counter += 1
