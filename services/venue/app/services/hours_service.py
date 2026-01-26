"""
=============================================================================
FILE: services/hours_service.py
PURPOSE: Venue operating hours management
=============================================================================
"""

from datetime import datetime, date, time
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.venue import VenueHours, VenueSpecialHours
from app.schemas.venue import (
    VenueHoursCreate,
    VenueHoursUpdate,
    VenueSpecialHoursCreate,
)

logger = structlog.get_logger()


class HoursService:
    """Service for venue hours management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Regular Hours
    # =========================================================================

    async def get_hours(self, venue_id: UUID) -> List[VenueHours]:
        """Get all regular hours for a venue."""
        result = await self.db.execute(
            select(VenueHours)
            .where(VenueHours.venue_id == venue_id)
            .order_by(VenueHours.day_of_week)
        )
        return list(result.scalars().all())

    async def set_hours(
        self,
        venue_id: UUID,
        hours_list: List[VenueHoursCreate],
    ) -> List[VenueHours]:
        """
        Set regular hours for a venue (replaces existing).

        Args:
            venue_id: Venue UUID
            hours_list: List of hours for each day

        Returns:
            Created hours records
        """
        # Delete existing hours
        await self.db.execute(
            delete(VenueHours).where(VenueHours.venue_id == venue_id)
        )

        # Create new hours
        created_hours = []
        for hours_data in hours_list:
            hours = VenueHours(
                venue_id=venue_id,
                day_of_week=hours_data.day_of_week,
                open_time=hours_data.open_time,
                close_time=hours_data.close_time,
                is_closed=hours_data.is_closed,
                is_24_hours=hours_data.is_24_hours,
            )
            self.db.add(hours)
            created_hours.append(hours)

        await self.db.flush()

        logger.info(
            "venue_hours_set",
            venue_id=str(venue_id),
            days_set=len(created_hours),
        )

        return created_hours

    async def update_day_hours(
        self,
        venue_id: UUID,
        day_of_week: int,
        update_data: VenueHoursUpdate,
    ) -> Optional[VenueHours]:
        """Update hours for a specific day."""
        result = await self.db.execute(
            select(VenueHours).where(
                VenueHours.venue_id == venue_id,
                VenueHours.day_of_week == day_of_week,
            )
        )
        hours = result.scalar_one_or_none()

        if not hours:
            # Create new record
            hours = VenueHours(
                venue_id=venue_id,
                day_of_week=day_of_week,
            )
            self.db.add(hours)

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(hours, field, value)

        await self.db.flush()
        await self.db.refresh(hours)

        return hours

    async def is_open(
        self,
        venue_id: UUID,
        check_date: Optional[date] = None,
        check_time: Optional[time] = None,
    ) -> bool:
        """
        Check if venue is open at given date/time.

        Args:
            venue_id: Venue UUID
            check_date: Date to check (defaults to today)
            check_time: Time to check (defaults to now)

        Returns:
            True if venue is open
        """
        check_date = check_date or date.today()
        check_time = check_time or datetime.now().time()

        # Check special hours first
        special = await self.get_special_hours_for_date(venue_id, check_date)
        if special:
            if special.is_closed:
                return False
            if special.is_24_hours:
                return True
            if special.open_time and special.close_time:
                return special.open_time <= check_time <= special.close_time
            return False

        # Check regular hours
        day_of_week = check_date.weekday()
        # Convert Python weekday (0=Monday) to our format (0=Sunday)
        day_of_week = (day_of_week + 1) % 7

        result = await self.db.execute(
            select(VenueHours).where(
                VenueHours.venue_id == venue_id,
                VenueHours.day_of_week == day_of_week,
            )
        )
        hours = result.scalar_one_or_none()

        if not hours:
            return False

        if hours.is_closed:
            return False

        if hours.is_24_hours:
            return True

        if hours.open_time and hours.close_time:
            # Handle overnight hours
            if hours.close_time < hours.open_time:
                return check_time >= hours.open_time or check_time <= hours.close_time
            return hours.open_time <= check_time <= hours.close_time

        return False

    # =========================================================================
    # Special Hours
    # =========================================================================

    async def get_special_hours(
        self,
        venue_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[VenueSpecialHours]:
        """Get special hours for a venue within date range."""
        query = select(VenueSpecialHours).where(
            VenueSpecialHours.venue_id == venue_id
        )

        if start_date:
            query = query.where(VenueSpecialHours.date >= start_date)
        if end_date:
            query = query.where(VenueSpecialHours.date <= end_date)

        query = query.order_by(VenueSpecialHours.date)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_special_hours_for_date(
        self,
        venue_id: UUID,
        check_date: date,
    ) -> Optional[VenueSpecialHours]:
        """Get special hours for a specific date."""
        result = await self.db.execute(
            select(VenueSpecialHours).where(
                VenueSpecialHours.venue_id == venue_id,
                VenueSpecialHours.date == check_date,
            )
        )
        return result.scalar_one_or_none()

    async def create_special_hours(
        self,
        venue_id: UUID,
        special_data: VenueSpecialHoursCreate,
    ) -> VenueSpecialHours:
        """Create special hours for a date."""
        # Remove existing special hours for this date
        await self.db.execute(
            delete(VenueSpecialHours).where(
                VenueSpecialHours.venue_id == venue_id,
                VenueSpecialHours.date == special_data.date,
            )
        )

        special = VenueSpecialHours(
            venue_id=venue_id,
            date=special_data.date,
            name=special_data.name,
            open_time=special_data.open_time,
            close_time=special_data.close_time,
            is_closed=special_data.is_closed,
            is_24_hours=special_data.is_24_hours,
            notes=special_data.notes,
        )
        self.db.add(special)
        await self.db.flush()
        await self.db.refresh(special)

        logger.info(
            "special_hours_created",
            venue_id=str(venue_id),
            date=str(special_data.date),
            name=special_data.name,
        )

        return special

    async def delete_special_hours(
        self,
        venue_id: UUID,
        special_id: UUID,
    ) -> bool:
        """Delete special hours by ID."""
        result = await self.db.execute(
            select(VenueSpecialHours).where(
                VenueSpecialHours.id == special_id,
                VenueSpecialHours.venue_id == venue_id,
            )
        )
        special = result.scalar_one_or_none()

        if not special:
            return False

        await self.db.delete(special)
        await self.db.flush()

        return True
