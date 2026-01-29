"""Recurring reservation management service."""

import uuid as uuid_module
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, bad_request
from app.models.reservation import (
    Reservation,
    ReservationItem,
    ReservationStatus,
    RecurrenceFrequency,
)
from app.schemas.reservation import RecurringReservationCreate
from app.services.event_publisher import EventPublisher, EventType
from app.services.reservation_service import ReservationService

logger = structlog.get_logger()

MAX_RECURRING_OCCURRENCES = 52  # 1 year of weekly


class RecurringReservationService:
    """Manages recurring reservation series (weekly, biweekly, monthly)."""

    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher
        self._reservation_service = ReservationService(db, event_publisher)

    async def create_recurring_series(
        self, venue_id: UUID, data: RecurringReservationCreate
    ) -> List[Reservation]:
        """Create a series of recurring reservations."""
        # Validate
        if data.recurrence_end_date and data.recurrence_end_date <= data.reservation_date:
            raise bad_request(
                ErrorCode.RECURRING_END_BEFORE_START,
                "Recurrence end date must be after the first reservation date.",
            )

        dates = self._generate_dates(
            data.reservation_date,
            data.recurrence_frequency,
            data.recurrence_end_date,
            data.max_occurrences,
        )

        if len(dates) > MAX_RECURRING_OCCURRENCES:
            raise bad_request(
                ErrorCode.RECURRING_MAX_OCCURRENCES_EXCEEDED,
                f"Recurring series cannot exceed {MAX_RECURRING_OCCURRENCES} occurrences.",
                {"max_occurrences": MAX_RECURRING_OCCURRENCES},
            )

        group_id = uuid_module.uuid4()
        created: List[Reservation] = []

        for idx, res_date in enumerate(dates):
            reservation = Reservation(
                venue_id=venue_id,
                customer_id=data.customer_id,
                reservation_type=data.reservation_type.value,
                reservation_date=res_date,
                start_time=data.start_time,
                end_time=data.end_time,
                party_size=data.party_size,
                status=ReservationStatus.PENDING.value,
                confirmation_code=self._reservation_service._generate_confirmation_code(),
                booking_channel=data.booking_channel.value if data.booking_channel else None,
                special_requests=data.special_requests,
                deposit_required=data.deposit_required,
                deposit_amount=data.deposit_amount,
                is_recurring=True,
                recurrence_group_id=group_id,
                recurrence_frequency=data.recurrence_frequency.value,
                recurrence_end_date=data.recurrence_end_date,
                recurrence_index=idx,
            )
            self.db.add(reservation)
            await self.db.flush()

            # Add items
            for item_data in data.items:
                item = ReservationItem(
                    reservation_id=reservation.id,
                    item_type=item_data.item_type.value,
                    item_id=item_data.item_id,
                    quantity=item_data.quantity,
                    duration_minutes=item_data.duration_minutes,
                    base_price=item_data.base_price,
                    dynamic_price=item_data.dynamic_price,
                )
                self.db.add(item)

            created.append(reservation)

        await self.db.commit()
        for res in created:
            await self.db.refresh(res)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CREATED,
                {
                    "type": "recurring_series",
                    "recurrence_group_id": str(group_id),
                    "frequency": data.recurrence_frequency.value,
                    "count": len(created),
                    "first_date": str(dates[0]),
                    "last_date": str(dates[-1]),
                },
                venue_id=venue_id,
            )

        logger.info(
            "recurring_series_created",
            group_id=str(group_id),
            count=len(created),
        )
        return created

    async def get_series(self, recurrence_group_id: UUID) -> List[Reservation]:
        """Get all reservations in a recurring series."""
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.recurrence_group_id == recurrence_group_id)
            .order_by(Reservation.reservation_date, Reservation.start_time)
        )
        return list(result.scalars().all())

    async def cancel_series(
        self, recurrence_group_id: UUID, cancel_future_only: bool = False
    ) -> List[Reservation]:
        """Cancel all (or future) reservations in a recurring series."""
        query = select(Reservation).where(
            and_(
                Reservation.recurrence_group_id == recurrence_group_id,
                Reservation.status.in_([
                    ReservationStatus.PENDING.value,
                    ReservationStatus.CONFIRMED.value,
                ]),
            )
        )
        if cancel_future_only:
            query = query.where(Reservation.reservation_date >= date.today())

        result = await self.db.execute(query)
        reservations = list(result.scalars().all())

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for res in reservations:
            res.status = ReservationStatus.CANCELLED.value
            res.cancelled_at = now

        await self.db.commit()
        for res in reservations:
            await self.db.refresh(res)

        logger.info(
            "recurring_series_cancelled",
            group_id=str(recurrence_group_id),
            count=len(reservations),
            future_only=cancel_future_only,
        )
        return reservations

    def _generate_dates(
        self,
        start_date: date,
        frequency: RecurrenceFrequency,
        end_date: Optional[date] = None,
        max_occurrences: Optional[int] = None,
    ) -> List[date]:
        """Generate a list of dates for the recurrence pattern."""
        dates = [start_date]
        current = start_date

        if not max_occurrences:
            max_occurrences = MAX_RECURRING_OCCURRENCES
        if not end_date:
            # Default: 3 months for weekly, 6 months for biweekly, 12 months for monthly
            if frequency == RecurrenceFrequency.WEEKLY:
                end_date = start_date + timedelta(weeks=12)
            elif frequency == RecurrenceFrequency.BIWEEKLY:
                end_date = start_date + timedelta(weeks=24)
            else:
                end_date = start_date + timedelta(days=365)

        while len(dates) < max_occurrences:
            if frequency == RecurrenceFrequency.WEEKLY:
                current = current + timedelta(weeks=1)
            elif frequency == RecurrenceFrequency.BIWEEKLY:
                current = current + timedelta(weeks=2)
            elif frequency == RecurrenceFrequency.MONTHLY:
                # Add roughly a month
                month = current.month + 1
                year = current.year
                if month > 12:
                    month = 1
                    year += 1
                day = min(current.day, 28)  # Safe day for all months
                current = date(year, month, day)

            if current > end_date:
                break
            dates.append(current)

        return dates
