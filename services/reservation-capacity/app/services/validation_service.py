"""Reservation input validation and conflict detection service."""

import structlog
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ErrorCode, ServiceError, bad_request, conflict
from app.models.reservation import (
    CapacityConfig,
    Reservation,
    ReservationItem,
    ReservationStatus,
    TimeSlotAvailability,
)
from app.schemas.reservation import ReservationCreate

logger = structlog.get_logger()
settings = get_settings()


class ValidationService:
    """Validates reservation data and detects conflicts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_reservation(
        self, venue_id: UUID, data: ReservationCreate
    ) -> None:
        """Run all validation checks before creating a reservation.
        Raises ServiceError if any check fails.
        """
        self._validate_date_not_in_past(data.reservation_date)
        self._validate_time_range(data.start_time, data.end_time)
        await self._validate_advance_booking(venue_id, data)
        await self._validate_party_size(venue_id, data)
        await self._validate_business_hours(venue_id, data)
        await self._check_capacity_available(venue_id, data)
        await self._check_double_booking(venue_id, data)

    def _validate_date_not_in_past(self, reservation_date: date) -> None:
        """Prevent bookings for past dates."""
        today = date.today()
        if reservation_date < today:
            raise bad_request(
                ErrorCode.RESERVATION_PAST_DATE,
                f"Cannot create reservation for past date {reservation_date}. Today is {today}.",
            )

    def _validate_time_range(self, start_time: time, end_time: time) -> None:
        """Ensure start_time < end_time."""
        if start_time >= end_time:
            raise bad_request(
                ErrorCode.RESERVATION_INVALID_TIME_RANGE,
                f"Start time ({start_time}) must be before end time ({end_time}).",
            )

    async def _validate_advance_booking(
        self, venue_id: UUID, data: ReservationCreate
    ) -> None:
        """Check min/max advance booking constraints from capacity config."""
        # Get capacity config for any item type in the reservation
        resource_type = data.items[0].item_type.value if data.items else data.reservation_type.value
        result = await self.db.execute(
            select(CapacityConfig).where(
                and_(
                    CapacityConfig.venue_id == venue_id,
                    CapacityConfig.resource_type == resource_type,
                )
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            return  # No config means no constraints

        now = datetime.now(timezone.utc)
        reservation_dt = datetime.combine(data.reservation_date, data.start_time, tzinfo=timezone.utc)
        minutes_until = (reservation_dt - now).total_seconds() / 60

        if minutes_until < config.min_advance_booking_minutes:
            raise bad_request(
                ErrorCode.RESERVATION_INSUFFICIENT_ADVANCE,
                f"Reservation must be booked at least {config.min_advance_booking_minutes} minutes in advance.",
                {"min_advance_minutes": config.min_advance_booking_minutes},
            )

        days_until = (data.reservation_date - date.today()).days
        if days_until > config.max_advance_booking_days:
            raise bad_request(
                ErrorCode.RESERVATION_TOO_FAR_ADVANCE,
                f"Reservation cannot be booked more than {config.max_advance_booking_days} days in advance.",
                {"max_advance_days": config.max_advance_booking_days},
            )

    async def _validate_party_size(
        self, venue_id: UUID, data: ReservationCreate
    ) -> None:
        """Validate party size against resource max_party_size."""
        resource_type = data.items[0].item_type.value if data.items else data.reservation_type.value
        result = await self.db.execute(
            select(CapacityConfig).where(
                and_(
                    CapacityConfig.venue_id == venue_id,
                    CapacityConfig.resource_type == resource_type,
                )
            )
        )
        config = result.scalar_one_or_none()
        if config and data.party_size > config.max_party_size:
            raise bad_request(
                ErrorCode.RESERVATION_PARTY_SIZE_EXCEEDED,
                f"Party size {data.party_size} exceeds maximum allowed ({config.max_party_size}).",
                {"max_party_size": config.max_party_size},
            )

    async def _validate_business_hours(
        self, venue_id: UUID, data: ReservationCreate
    ) -> None:
        """Check reservation falls within business hours."""
        resource_type = data.items[0].item_type.value if data.items else data.reservation_type.value
        result = await self.db.execute(
            select(CapacityConfig).where(
                and_(
                    CapacityConfig.venue_id == venue_id,
                    CapacityConfig.resource_type == resource_type,
                )
            )
        )
        config = result.scalar_one_or_none()
        if not config or not config.business_hours_start or not config.business_hours_end:
            return  # No business hours configured

        if data.start_time < config.business_hours_start or data.end_time > config.business_hours_end:
            raise bad_request(
                ErrorCode.RESERVATION_OUTSIDE_BUSINESS_HOURS,
                f"Reservation must be within business hours ({config.business_hours_start} - {config.business_hours_end}).",
                {
                    "business_hours_start": str(config.business_hours_start),
                    "business_hours_end": str(config.business_hours_end),
                },
            )

    async def _check_capacity_available(
        self, venue_id: UUID, data: ReservationCreate
    ) -> None:
        """Check that there is available capacity for the requested slot."""
        for item in data.items:
            result = await self.db.execute(
                select(TimeSlotAvailability).where(
                    and_(
                        TimeSlotAvailability.venue_id == venue_id,
                        TimeSlotAvailability.resource_type == item.item_type.value,
                        TimeSlotAvailability.availability_date == data.reservation_date,
                        TimeSlotAvailability.time_slot == data.start_time,
                    )
                )
            )
            slot = result.scalar_one_or_none()
            if slot and slot.available_capacity < item.quantity:
                raise conflict(
                    ErrorCode.CAPACITY_EXCEEDED,
                    f"Insufficient capacity for {item.item_type.value} on {data.reservation_date} at {data.start_time}.",
                    {
                        "resource_type": item.item_type.value,
                        "requested": item.quantity,
                        "available": slot.available_capacity,
                    },
                )

    async def _check_double_booking(
        self, venue_id: UUID, data: ReservationCreate
    ) -> None:
        """Detect conflicting reservations for the same customer at overlapping times."""
        if not data.customer_id:
            return

        result = await self.db.execute(
            select(Reservation).where(
                and_(
                    Reservation.venue_id == venue_id,
                    Reservation.customer_id == data.customer_id,
                    Reservation.reservation_date == data.reservation_date,
                    Reservation.status.in_([
                        ReservationStatus.PENDING.value,
                        ReservationStatus.CONFIRMED.value,
                    ]),
                    # Overlapping time: existing.start < new.end AND existing.end > new.start
                    Reservation.start_time < data.end_time,
                    Reservation.end_time > data.start_time,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise conflict(
                ErrorCode.DOUBLE_BOOKING_DETECTED,
                f"Customer already has a reservation at an overlapping time on {data.reservation_date}.",
                {
                    "existing_reservation_id": str(existing.id),
                    "existing_confirmation_code": existing.confirmation_code,
                    "existing_time": f"{existing.start_time}-{existing.end_time}",
                },
            )

    async def check_resource_conflict(
        self, venue_id: UUID, resource_id: UUID, reservation_date: date,
        start_time: time, end_time: time, exclude_reservation_id: Optional[UUID] = None,
    ) -> None:
        """Check if a specific resource (e.g., lane #3) is already booked at the given time."""
        query = (
            select(ReservationItem)
            .join(Reservation, ReservationItem.reservation_id == Reservation.id)
            .where(
                and_(
                    Reservation.venue_id == venue_id,
                    Reservation.reservation_date == reservation_date,
                    Reservation.status.in_([
                        ReservationStatus.PENDING.value,
                        ReservationStatus.CONFIRMED.value,
                        ReservationStatus.CHECKED_IN.value,
                    ]),
                    Reservation.start_time < end_time,
                    Reservation.end_time > start_time,
                    ReservationItem.assigned_resource_id == resource_id,
                )
            )
        )
        if exclude_reservation_id:
            query = query.where(Reservation.id != exclude_reservation_id)

        result = await self.db.execute(query)
        conflicting = result.scalar_one_or_none()
        if conflicting:
            raise conflict(
                ErrorCode.RESOURCE_CONFLICT,
                f"Resource {resource_id} is already booked during the requested time.",
                {
                    "resource_id": str(resource_id),
                    "conflicting_reservation_id": str(conflicting.reservation_id),
                },
            )
