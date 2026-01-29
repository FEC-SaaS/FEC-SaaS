"""Waitlist management service."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.reservation import ReservationWaitlist, WaitlistStatus
from app.schemas.reservation import WaitlistCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()
settings = get_settings()


class WaitlistService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def list_waitlist(
        self, venue_id: UUID, reservation_type: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> Tuple[List[ReservationWaitlist], int]:
        base_query = select(ReservationWaitlist).where(
            ReservationWaitlist.venue_id == venue_id,
            ReservationWaitlist.status == WaitlistStatus.WAITING.value,
        )
        if reservation_type:
            base_query = base_query.where(ReservationWaitlist.reservation_type == reservation_type)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(
            ReservationWaitlist.priority.desc(), ReservationWaitlist.created_at
        ).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def add_to_waitlist(self, venue_id: UUID, data: WaitlistCreate) -> ReservationWaitlist:
        # VIP members could get higher priority (default 0)
        entry = ReservationWaitlist(
            venue_id=venue_id,
            customer_id=data.customer_id,
            reservation_type=data.reservation_type.value,
            desired_date=data.desired_date,
            desired_time=data.desired_time,
            party_size=data.party_size,
            notes=data.notes,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.WAITLIST_ADDED,
                {"waitlist_id": str(entry.id), "customer_id": str(data.customer_id) if data.customer_id else None},
                venue_id=venue_id,
            )
        logger.info("waitlist_entry_added", waitlist_id=str(entry.id))
        return entry

    async def remove_from_waitlist(self, waitlist_id: UUID) -> Optional[ReservationWaitlist]:
        result = await self.db.execute(
            select(ReservationWaitlist).where(ReservationWaitlist.id == waitlist_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        entry.status = WaitlistStatus.CANCELLED.value
        await self.db.commit()
        await self.db.refresh(entry)
        logger.info("waitlist_entry_cancelled", waitlist_id=str(waitlist_id))
        return entry

    async def notify_customer(self, waitlist_id: UUID) -> Optional[ReservationWaitlist]:
        result = await self.db.execute(
            select(ReservationWaitlist).where(ReservationWaitlist.id == waitlist_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        entry.status = WaitlistStatus.NOTIFIED.value
        entry.notified_at = datetime.now(timezone.utc)
        entry.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        await self.db.commit()
        await self.db.refresh(entry)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.WAITLIST_NOTIFIED,
                {"waitlist_id": str(waitlist_id), "customer_id": str(entry.customer_id) if entry.customer_id else None},
                venue_id=entry.venue_id,
            )
        logger.info("waitlist_customer_notified", waitlist_id=str(waitlist_id))
        return entry

    async def convert_to_reservation(self, waitlist_id: UUID) -> Optional[ReservationWaitlist]:
        result = await self.db.execute(
            select(ReservationWaitlist).where(ReservationWaitlist.id == waitlist_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        entry.status = WaitlistStatus.CONVERTED.value
        await self.db.commit()
        await self.db.refresh(entry)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.WAITLIST_CONVERTED,
                {"waitlist_id": str(waitlist_id)},
                venue_id=entry.venue_id,
            )
        logger.info("waitlist_converted", waitlist_id=str(waitlist_id))
        return entry
