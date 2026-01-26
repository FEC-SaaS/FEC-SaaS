"""
=============================================================================
FILE: services/booking_service.py
PURPOSE: Party booking management business logic
=============================================================================
"""

import secrets
import string
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.party import (
    PartyBooking,
    PartyBookingAddon,
    PartyPackage,
    PartyAddon,
    PartyTimeline,
    BookingStatus,
    BookingType,
    TimelineStatus,
)
from app.schemas.party import (
    PartyBookingCreate,
    PartyBookingUpdate,
    PartyBookingStatusUpdate,
    BookingAddonCreate,
    PaginationParams,
)
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class BookingService:
    """Service for party booking management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_booking_reference(self) -> str:
        """Generate unique booking reference."""
        chars = string.ascii_uppercase + string.digits
        return "PB-" + "".join(secrets.choice(chars) for _ in range(8))

    async def _calculate_end_time(self, start_time: time, duration_minutes: int) -> time:
        """Calculate end time from start time and duration."""
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        return end_dt.time()

    async def _create_default_timeline(
        self,
        booking: PartyBooking,
        package: PartyPackage,
    ) -> List[PartyTimeline]:
        """Create default timeline items based on package settings."""
        timeline_items = []
        start_dt = datetime.combine(booking.party_date, booking.start_time)
        current_time = start_dt

        # Welcome and check-in
        timeline_items.append(PartyTimeline(
            booking_id=booking.id,
            item_name="Guest arrival and check-in",
            item_category="setup",
            scheduled_time=current_time.time(),
            duration_minutes=15,
            sequence_order=1,
        ))
        current_time += timedelta(minutes=15)

        # Activities (first half)
        activity_duration = (package.duration_minutes - 45) // 2
        timeline_items.append(PartyTimeline(
            booking_id=booking.id,
            item_name="Activities - Part 1",
            item_category="activity",
            scheduled_time=current_time.time(),
            duration_minutes=activity_duration,
            sequence_order=2,
        ))
        current_time += timedelta(minutes=activity_duration)

        # Food service
        if package.includes_food:
            timeline_items.append(PartyTimeline(
                booking_id=booking.id,
                item_name="Food service",
                item_category="food",
                scheduled_time=current_time.time(),
                duration_minutes=30,
                sequence_order=3,
            ))
            current_time += timedelta(minutes=30)

        # Cake and singing (if applicable)
        if package.includes_cake:
            timeline_items.append(PartyTimeline(
                booking_id=booking.id,
                item_name="Cake and celebration",
                item_category="celebration",
                scheduled_time=current_time.time(),
                duration_minutes=15,
                sequence_order=4,
            ))
            current_time += timedelta(minutes=15)

        # Activities (second half)
        timeline_items.append(PartyTimeline(
            booking_id=booking.id,
            item_name="Activities - Part 2",
            item_category="activity",
            scheduled_time=current_time.time(),
            duration_minutes=activity_duration,
            sequence_order=5,
        ))
        current_time += timedelta(minutes=activity_duration)

        # Wrap-up
        timeline_items.append(PartyTimeline(
            booking_id=booking.id,
            item_name="Wrap-up and departure",
            item_category="closing",
            scheduled_time=current_time.time(),
            duration_minutes=15,
            sequence_order=6,
        ))

        for item in timeline_items:
            self.db.add(item)

        return timeline_items

    async def create_booking(self, booking_data: PartyBookingCreate) -> PartyBooking:
        """
        Create a new party booking.

        Args:
            booking_data: Booking creation data

        Returns:
            Created booking instance
        """
        # Get package details
        package_result = await self.db.execute(
            select(PartyPackage).where(PartyPackage.id == booking_data.package_id)
        )
        package = package_result.scalar_one_or_none()
        if not package:
            raise ValueError("Package not found")

        # Calculate end time
        end_time = await self._calculate_end_time(
            booking_data.start_time,
            package.duration_minutes,
        )

        # Calculate pricing
        base_price = package.base_price
        additional_guests = max(0, booking_data.guest_count - package.min_guests)
        if package.price_per_additional_guest and additional_guests > 0:
            base_price += package.price_per_additional_guest * additional_guests

        # Calculate deposit
        deposit_amount = base_price * (package.deposit_percentage / 100)

        # Generate booking reference
        booking_reference = self._generate_booking_reference()

        # Ensure unique reference
        while True:
            existing = await self.db.execute(
                select(PartyBooking).where(
                    PartyBooking.booking_reference == booking_reference
                )
            )
            if not existing.scalar_one_or_none():
                break
            booking_reference = self._generate_booking_reference()

        booking = PartyBooking(
            venue_id=booking_data.venue_id,
            customer_id=booking_data.customer_id,
            package_id=booking_data.package_id,
            booking_type=booking_data.booking_type,
            booking_reference=booking_reference,
            party_date=booking_data.party_date,
            start_time=booking_data.start_time,
            end_time=end_time,
            guest_count=booking_data.guest_count,
            child_count=booking_data.child_count,
            adult_count=booking_data.adult_count,
            guest_of_honor_name=booking_data.guest_of_honor_name,
            guest_of_honor_age=booking_data.guest_of_honor_age,
            contact_name=booking_data.contact_name,
            contact_email=booking_data.contact_email,
            contact_phone=booking_data.contact_phone,
            base_price=base_price,
            addons_total=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_price=base_price,
            deposit_amount=deposit_amount,
            balance_due=base_price,
            status=BookingStatus.PENDING,
            special_requests=booking_data.special_requests,
            dietary_restrictions=booking_data.dietary_restrictions,
            allergy_info=booking_data.allergy_info,
            booking_source=booking_data.booking_source,
        )

        self.db.add(booking)
        await self.db.flush()

        # Add addons if provided
        if booking_data.addons:
            addons_total = Decimal("0.00")
            for addon_data in booking_data.addons:
                addon_result = await self.db.execute(
                    select(PartyAddon).where(PartyAddon.id == addon_data.addon_id)
                )
                addon = addon_result.scalar_one_or_none()
                if addon:
                    unit_price = addon.price
                    if addon.price_type == "per_guest":
                        unit_price = addon.price * booking_data.guest_count
                    total_price = unit_price * addon_data.quantity

                    booking_addon = PartyBookingAddon(
                        booking_id=booking.id,
                        addon_id=addon_data.addon_id,
                        quantity=addon_data.quantity,
                        unit_price=unit_price,
                        total_price=total_price,
                        notes=addon_data.notes,
                    )
                    self.db.add(booking_addon)
                    addons_total += total_price

            booking.addons_total = addons_total
            booking.total_price = base_price + addons_total
            booking.balance_due = booking.total_price

        # Create default timeline if enabled
        if settings.ENABLE_AUTO_TIMELINE:
            await self._create_default_timeline(booking, package)

        await self.db.flush()
        await self.db.refresh(booking)

        logger.info(
            "booking_created",
            booking_id=str(booking.id),
            booking_reference=booking.booking_reference,
            venue_id=str(booking.venue_id),
            party_date=str(booking.party_date),
        )

        return booking

    async def get_booking(self, booking_id: UUID) -> Optional[PartyBooking]:
        """Get booking by ID with all related data."""
        result = await self.db.execute(
            select(PartyBooking)
            .options(
                selectinload(PartyBooking.addons),
                selectinload(PartyBooking.timeline),
                selectinload(PartyBooking.host_assignments),
                selectinload(PartyBooking.package),
            )
            .where(
                and_(
                    PartyBooking.id == booking_id,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_booking_by_reference(self, reference: str) -> Optional[PartyBooking]:
        """Get booking by reference code."""
        result = await self.db.execute(
            select(PartyBooking)
            .options(
                selectinload(PartyBooking.addons),
                selectinload(PartyBooking.timeline),
            )
            .where(
                and_(
                    PartyBooking.booking_reference == reference,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_bookings(
        self,
        venue_id: UUID,
        pagination: PaginationParams,
        status: Optional[BookingStatus] = None,
        booking_type: Optional[BookingType] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        customer_id: Optional[UUID] = None,
    ) -> Tuple[List[PartyBooking], int]:
        """List bookings with filtering and pagination."""
        query = select(PartyBooking).where(
            and_(
                PartyBooking.venue_id == venue_id,
                PartyBooking.is_deleted == False,
            )
        )

        if status:
            query = query.where(PartyBooking.status == status)

        if booking_type:
            query = query.where(PartyBooking.booking_type == booking_type)

        if date_from:
            query = query.where(PartyBooking.party_date >= date_from)

        if date_to:
            query = query.where(PartyBooking.party_date <= date_to)

        if customer_id:
            query = query.where(PartyBooking.customer_id == customer_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(PartyBooking, pagination.sort_by, PartyBooking.party_date)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        bookings = list(result.scalars().all())

        return bookings, total

    async def update_booking(
        self,
        booking_id: UUID,
        update_data: PartyBookingUpdate,
    ) -> Optional[PartyBooking]:
        """Update booking information."""
        booking = await self.get_booking(booking_id)
        if not booking:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(booking, field, value)

        booking.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(booking)

        logger.info(
            "booking_updated",
            booking_id=str(booking_id),
            fields_updated=list(update_dict.keys()),
        )

        return booking

    async def update_booking_status(
        self,
        booking_id: UUID,
        status_update: PartyBookingStatusUpdate,
    ) -> Optional[PartyBooking]:
        """Update booking status with workflow validation."""
        booking = await self.get_booking(booking_id)
        if not booking:
            return None

        old_status = booking.status
        new_status = status_update.status

        # Update status
        booking.status = new_status
        booking.updated_at = datetime.utcnow()

        # Set timestamps based on status
        if new_status == BookingStatus.CONFIRMED:
            booking.confirmed_at = datetime.utcnow()
        elif new_status == BookingStatus.CHECKED_IN:
            booking.checked_in_at = datetime.utcnow()
        elif new_status == BookingStatus.COMPLETED:
            booking.completed_at = datetime.utcnow()
        elif new_status == BookingStatus.CANCELLED:
            booking.cancelled_at = datetime.utcnow()
            booking.cancellation_reason = status_update.cancellation_reason

        await self.db.flush()
        await self.db.refresh(booking)

        logger.info(
            "booking_status_changed",
            booking_id=str(booking_id),
            old_status=old_status.value,
            new_status=new_status.value,
        )

        return booking

    async def add_booking_addon(
        self,
        booking_id: UUID,
        addon_data: BookingAddonCreate,
    ) -> Optional[PartyBookingAddon]:
        """Add an addon to a booking."""
        booking = await self.get_booking(booking_id)
        if not booking:
            return None

        addon_result = await self.db.execute(
            select(PartyAddon).where(PartyAddon.id == addon_data.addon_id)
        )
        addon = addon_result.scalar_one_or_none()
        if not addon:
            return None

        unit_price = addon.price
        if addon.price_type == "per_guest":
            unit_price = addon.price * booking.guest_count
        total_price = unit_price * addon_data.quantity

        booking_addon = PartyBookingAddon(
            booking_id=booking_id,
            addon_id=addon_data.addon_id,
            quantity=addon_data.quantity,
            unit_price=unit_price,
            total_price=total_price,
            notes=addon_data.notes,
        )

        self.db.add(booking_addon)

        # Update booking totals
        booking.addons_total += total_price
        booking.total_price += total_price
        booking.balance_due = booking.total_price - booking.amount_paid
        booking.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(booking_addon)

        return booking_addon

    async def remove_booking_addon(
        self,
        booking_id: UUID,
        addon_id: UUID,
    ) -> bool:
        """Remove an addon from a booking."""
        result = await self.db.execute(
            select(PartyBookingAddon).where(
                and_(
                    PartyBookingAddon.booking_id == booking_id,
                    PartyBookingAddon.addon_id == addon_id,
                )
            )
        )
        booking_addon = result.scalar_one_or_none()
        if not booking_addon:
            return False

        booking = await self.get_booking(booking_id)
        if booking:
            booking.addons_total -= booking_addon.total_price
            booking.total_price -= booking_addon.total_price
            booking.balance_due = booking.total_price - booking.amount_paid
            booking.updated_at = datetime.utcnow()

        await self.db.delete(booking_addon)
        await self.db.flush()

        return True

    async def check_in_booking(self, booking_id: UUID) -> Optional[PartyBooking]:
        """Check in a party booking."""
        return await self.update_booking_status(
            booking_id,
            PartyBookingStatusUpdate(status=BookingStatus.CHECKED_IN),
        )

    async def complete_booking(self, booking_id: UUID) -> Optional[PartyBooking]:
        """Complete a party booking."""
        return await self.update_booking_status(
            booking_id,
            PartyBookingStatusUpdate(status=BookingStatus.COMPLETED),
        )

    async def cancel_booking(
        self,
        booking_id: UUID,
        cancellation_reason: Optional[str] = None,
    ) -> Optional[PartyBooking]:
        """Cancel a party booking."""
        return await self.update_booking_status(
            booking_id,
            PartyBookingStatusUpdate(
                status=BookingStatus.CANCELLED,
                cancellation_reason=cancellation_reason,
            ),
        )

    async def delete_booking(self, booking_id: UUID) -> bool:
        """Soft delete a booking."""
        booking = await self.get_booking(booking_id)
        if not booking:
            return False

        booking.is_deleted = True
        booking.deleted_at = datetime.utcnow()
        await self.db.flush()

        logger.info("booking_deleted", booking_id=str(booking_id))
        return True

    async def get_today_bookings(self, venue_id: UUID) -> List[PartyBooking]:
        """Get all bookings for today at a venue."""
        today = date.today()
        result = await self.db.execute(
            select(PartyBooking)
            .options(
                selectinload(PartyBooking.timeline),
                selectinload(PartyBooking.host_assignments),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date == today,
                    PartyBooking.is_deleted == False,
                    PartyBooking.status.not_in([
                        BookingStatus.CANCELLED,
                        BookingStatus.NO_SHOW,
                    ]),
                )
            )
            .order_by(PartyBooking.start_time)
        )
        return list(result.scalars().all())

    async def check_availability(
        self,
        venue_id: UUID,
        party_date: date,
        start_time: time,
        duration_minutes: int,
    ) -> bool:
        """Check if a time slot is available."""
        end_dt = datetime.combine(party_date, start_time) + timedelta(minutes=duration_minutes)
        end_time = end_dt.time()

        result = await self.db.execute(
            select(func.count())
            .select_from(PartyBooking)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date == party_date,
                    PartyBooking.is_deleted == False,
                    PartyBooking.status.not_in([
                        BookingStatus.CANCELLED,
                        BookingStatus.NO_SHOW,
                    ]),
                    or_(
                        and_(
                            PartyBooking.start_time <= start_time,
                            PartyBooking.end_time > start_time,
                        ),
                        and_(
                            PartyBooking.start_time < end_time,
                            PartyBooking.end_time >= end_time,
                        ),
                        and_(
                            PartyBooking.start_time >= start_time,
                            PartyBooking.end_time <= end_time,
                        ),
                    ),
                )
            )
        )
        count = result.scalar() or 0
        return count == 0
