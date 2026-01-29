"""Capacity management service."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.reservation import (
    CapacityConfig,
    TimeSlotAvailability,
    Reservation,
    ReservationStatus,
    TimeSlotHold,
    HoldStatus,
)
from app.schemas.reservation import CapacityConfigCreate, CapacityConfigUpdate, HoldRequest
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()
settings = get_settings()


class CapacityService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    # ─── Capacity Config ────────────────────────────────────────────────────

    async def list_configs(
        self,
        venue_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CapacityConfig], int]:
        """List capacity configurations for a venue with pagination."""
        base_query = select(CapacityConfig).where(CapacityConfig.venue_id == venue_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = (
            base_query
            .order_by(CapacityConfig.resource_type)
            .limit(page_size)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_config(
        self,
        venue_id: UUID,
        resource_type: str,
    ) -> Optional[CapacityConfig]:
        """Get a capacity configuration by venue and resource type."""
        result = await self.db.execute(
            select(CapacityConfig).where(
                and_(
                    CapacityConfig.venue_id == venue_id,
                    CapacityConfig.resource_type == resource_type,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update_config(
        self,
        venue_id: UUID,
        data: CapacityConfigCreate,
    ) -> CapacityConfig:
        """Create or update a capacity configuration (upsert)."""
        existing = await self.get_config(venue_id, data.resource_type.value)

        if existing:
            existing.total_capacity = data.total_capacity
            existing.buffer_percentage = data.buffer_percentage
            existing.overbooking_percentage = data.overbooking_percentage
            existing.min_advance_booking_minutes = data.min_advance_booking_minutes
            existing.max_advance_booking_days = data.max_advance_booking_days
            if data.business_hours_start is not None:
                existing.business_hours_start = data.business_hours_start
            if data.business_hours_end is not None:
                existing.business_hours_end = data.business_hours_end
            if data.max_party_size is not None:
                existing.max_party_size = data.max_party_size
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(
                "capacity_config_updated",
                venue_id=str(venue_id),
                resource_type=data.resource_type.value,
            )
            return existing

        config = CapacityConfig(
            venue_id=venue_id,
            resource_type=data.resource_type.value,
            total_capacity=data.total_capacity,
            buffer_percentage=data.buffer_percentage,
            overbooking_percentage=data.overbooking_percentage,
            min_advance_booking_minutes=data.min_advance_booking_minutes,
            max_advance_booking_days=data.max_advance_booking_days,
            business_hours_start=data.business_hours_start,
            business_hours_end=data.business_hours_end,
            max_party_size=data.max_party_size,
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        logger.info(
            "capacity_config_created",
            venue_id=str(venue_id),
            resource_type=data.resource_type.value,
        )
        return config

    # ─── Availability ───────────────────────────────────────────────────────

    async def get_availability(
        self,
        venue_id: UUID,
        resource_type: str,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[dict]:
        """Query time slot availability for a date range, grouped by date."""
        if end_date is None:
            end_date = start_date

        query = (
            select(TimeSlotAvailability)
            .where(
                and_(
                    TimeSlotAvailability.venue_id == venue_id,
                    TimeSlotAvailability.resource_type == resource_type,
                    TimeSlotAvailability.availability_date >= start_date,
                    TimeSlotAvailability.availability_date <= end_date,
                )
            )
            .order_by(TimeSlotAvailability.availability_date, TimeSlotAvailability.time_slot)
        )
        result = await self.db.execute(query)
        slots = list(result.scalars().all())

        # Group by date
        grouped: dict[date, list] = {}
        for slot in slots:
            if slot.availability_date not in grouped:
                grouped[slot.availability_date] = []
            grouped[slot.availability_date].append({
                "time_slot": slot.time_slot,
                "total_capacity": slot.total_capacity,
                "reserved_capacity": slot.reserved_capacity,
                "available_capacity": slot.available_capacity,
                "is_available": slot.is_available,
                "dynamic_price_multiplier": slot.dynamic_price_multiplier,
            })

        return [
            {
                "availability_date": avail_date,
                "resource_type": resource_type,
                "slots": date_slots,
            }
            for avail_date, date_slots in sorted(grouped.items())
        ]

    async def get_time_slots(
        self,
        venue_id: UUID,
        resource_type: str,
        target_date: date,
        party_size: Optional[int] = None,
    ) -> List[TimeSlotAvailability]:
        """Get time slots for a specific date, optionally filtered by party size."""
        query = (
            select(TimeSlotAvailability)
            .where(
                and_(
                    TimeSlotAvailability.venue_id == venue_id,
                    TimeSlotAvailability.resource_type == resource_type,
                    TimeSlotAvailability.availability_date == target_date,
                )
            )
            .order_by(TimeSlotAvailability.time_slot)
        )

        if party_size is not None:
            query = query.where(TimeSlotAvailability.available_capacity >= party_size)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ─── Real-Time Capacity ─────────────────────────────────────────────────

    async def get_real_time_capacity(
        self,
        venue_id: UUID,
        resource_type: str,
    ) -> dict:
        """Get real-time capacity for a venue resource type (today)."""
        today = date.today()

        # Get capacity config
        config = await self.get_config(venue_id, resource_type)
        total_capacity = config.total_capacity if config else 0

        # Count confirmed + checked-in reservations for today
        count_result = await self.db.execute(
            select(func.count()).select_from(
                select(Reservation)
                .where(
                    and_(
                        Reservation.venue_id == venue_id,
                        Reservation.reservation_date == today,
                        Reservation.status.in_([
                            ReservationStatus.CONFIRMED.value,
                            ReservationStatus.CHECKED_IN.value,
                        ]),
                    )
                )
                .subquery()
            )
        )
        currently_reserved = count_result.scalar() or 0
        currently_available = max(0, total_capacity - currently_reserved)
        utilization_percentage = (
            Decimal(str(currently_reserved)) / Decimal(str(total_capacity)) * Decimal("100")
            if total_capacity > 0
            else Decimal("0")
        )

        return {
            "venue_id": venue_id,
            "resource_type": resource_type,
            "total_capacity": total_capacity,
            "currently_reserved": currently_reserved,
            "currently_available": currently_available,
            "utilization_percentage": round(utilization_percentage, 2),
            "timestamp": datetime.now(timezone.utc),
        }

    # ─── Capacity Forecast ──────────────────────────────────────────────────

    async def get_capacity_forecast(
        self,
        venue_id: UUID,
        resource_type: str,
        forecast_date: date,
    ) -> dict:
        """Get capacity forecast for a future date."""
        slots = await self.get_time_slots(venue_id, resource_type, forecast_date)

        config = await self.get_config(venue_id, resource_type)
        total_capacity = config.total_capacity if config else 0

        forecast_slots = []
        for slot in slots:
            predicted_demand = slot.reserved_capacity
            available = slot.available_capacity
            utilization = (
                Decimal(str(predicted_demand)) / Decimal(str(slot.total_capacity)) * Decimal("100")
                if slot.total_capacity > 0
                else Decimal("0")
            )
            forecast_slots.append({
                "time_slot": slot.time_slot,
                "predicted_demand": predicted_demand,
                "available_capacity": available,
                "utilization_percentage": round(utilization, 2),
            })

        return {
            "venue_id": venue_id,
            "resource_type": resource_type,
            "forecast_date": forecast_date,
            "slots": forecast_slots,
        }

    # ─── Time Slot Holds ────────────────────────────────────────────────────

    async def hold_time_slot(
        self,
        venue_id: UUID,
        data: HoldRequest,
        held_by: Optional[UUID] = None,
    ) -> TimeSlotHold:
        """Create a temporary hold on a time slot."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.HOLD_EXPIRY_MINUTES)

        hold = TimeSlotHold(
            venue_id=venue_id,
            resource_type=data.resource_type.value,
            hold_date=data.hold_date,
            time_slot=data.time_slot,
            quantity=data.quantity,
            held_by=held_by,
            status=HoldStatus.ACTIVE.value,
            expires_at=expires_at,
        )
        self.db.add(hold)

        # Decrease available capacity in the time slot
        slot_result = await self.db.execute(
            select(TimeSlotAvailability).where(
                and_(
                    TimeSlotAvailability.venue_id == venue_id,
                    TimeSlotAvailability.resource_type == data.resource_type.value,
                    TimeSlotAvailability.availability_date == data.hold_date,
                    TimeSlotAvailability.time_slot == data.time_slot,
                )
            )
        )
        slot = slot_result.scalar_one_or_none()
        if slot:
            slot.available_capacity = max(0, slot.available_capacity - data.quantity)
            slot.reserved_capacity = slot.reserved_capacity + data.quantity
            slot.last_updated = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(hold)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.HOLD_CREATED,
                {
                    "hold_id": str(hold.id),
                    "venue_id": str(venue_id),
                    "resource_type": data.resource_type.value,
                    "hold_date": str(data.hold_date),
                    "time_slot": str(data.time_slot),
                    "quantity": data.quantity,
                    "expires_at": str(expires_at),
                },
                venue_id=venue_id,
            )
        logger.info("hold_created", hold_id=str(hold.id), venue_id=str(venue_id))
        return hold

    async def release_hold(self, hold_id: UUID) -> Optional[TimeSlotHold]:
        """Release an active hold and restore capacity."""
        result = await self.db.execute(
            select(TimeSlotHold).where(TimeSlotHold.id == hold_id)
        )
        hold = result.scalar_one_or_none()
        if not hold:
            return None

        hold.status = HoldStatus.RELEASED.value

        # Restore available capacity
        slot_result = await self.db.execute(
            select(TimeSlotAvailability).where(
                and_(
                    TimeSlotAvailability.venue_id == hold.venue_id,
                    TimeSlotAvailability.resource_type == hold.resource_type,
                    TimeSlotAvailability.availability_date == hold.hold_date,
                    TimeSlotAvailability.time_slot == hold.time_slot,
                )
            )
        )
        slot = slot_result.scalar_one_or_none()
        if slot:
            slot.available_capacity = slot.available_capacity + hold.quantity
            slot.reserved_capacity = max(0, slot.reserved_capacity - hold.quantity)
            slot.last_updated = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(hold)
        logger.info("hold_released", hold_id=str(hold_id))
        return hold

    async def _expire_holds(self) -> int:
        """Expire all active holds that have passed their expiry time and restore capacity."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(TimeSlotHold).where(
                and_(
                    TimeSlotHold.status == HoldStatus.ACTIVE.value,
                    TimeSlotHold.expires_at < now,
                )
            )
        )
        expired_holds = list(result.scalars().all())

        for hold in expired_holds:
            hold.status = HoldStatus.EXPIRED.value

            # Restore capacity
            slot_result = await self.db.execute(
                select(TimeSlotAvailability).where(
                    and_(
                        TimeSlotAvailability.venue_id == hold.venue_id,
                        TimeSlotAvailability.resource_type == hold.resource_type,
                        TimeSlotAvailability.availability_date == hold.hold_date,
                        TimeSlotAvailability.time_slot == hold.time_slot,
                    )
                )
            )
            slot = slot_result.scalar_one_or_none()
            if slot:
                slot.available_capacity = slot.available_capacity + hold.quantity
                slot.reserved_capacity = max(0, slot.reserved_capacity - hold.quantity)
                slot.last_updated = now

            logger.info(
                "hold_expired",
                hold_id=str(hold.id),
                venue_id=str(hold.venue_id),
                resource_type=hold.resource_type,
                hold_date=str(hold.hold_date),
                time_slot=str(hold.time_slot),
            )

        if expired_holds:
            await self.db.commit()
            logger.info("holds_expired_batch", count=len(expired_holds))

        return len(expired_holds)
