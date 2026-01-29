"""No-show tracking and management service."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import (
    CustomerReservationStats,
    NoShowHistory,
    Reservation,
    ReservationStatus,
)
from app.schemas.reservation import NoShowCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class NoShowService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def mark_no_show(
        self, reservation_id: UUID, data: Optional[NoShowCreate] = None,
    ) -> Optional[NoShowHistory]:
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        reservation = result.scalar_one_or_none()
        if not reservation:
            return None

        reservation.status = ReservationStatus.NO_SHOW.value

        no_show = NoShowHistory(
            customer_id=reservation.customer_id,
            reservation_id=reservation_id,
            no_show_date=reservation.reservation_date,
            reservation_value=data.reservation_value if data else None,
            reason=data.reason.value if data and data.reason else None,
        )
        self.db.add(no_show)
        await self.db.commit()
        await self.db.refresh(no_show)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_NO_SHOW,
                {
                    "reservation_id": str(reservation_id),
                    "customer_id": str(reservation.customer_id) if reservation.customer_id else None,
                    "date": str(reservation.reservation_date),
                },
                venue_id=reservation.venue_id,
            )
        logger.info("reservation_marked_no_show", reservation_id=str(reservation_id))
        return no_show

    async def list_no_shows(
        self, venue_id: UUID, start_date: Optional[date] = None,
        end_date: Optional[date] = None, page: int = 1, page_size: int = 20,
    ) -> Tuple[List[NoShowHistory], int]:
        base_query = (
            select(NoShowHistory)
            .join(Reservation, NoShowHistory.reservation_id == Reservation.id)
            .where(Reservation.venue_id == venue_id)
        )
        if start_date:
            base_query = base_query.where(NoShowHistory.no_show_date >= start_date)
        if end_date:
            base_query = base_query.where(NoShowHistory.no_show_date <= end_date)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(NoShowHistory.no_show_date.desc()).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_customer_history(self, customer_id: UUID) -> List[Reservation]:
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.customer_id == customer_id)
            .order_by(Reservation.reservation_date.desc(), Reservation.start_time.desc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_reliability_score(self, customer_id: UUID) -> Optional[CustomerReservationStats]:
        result = await self.db.execute(
            select(CustomerReservationStats)
            .where(CustomerReservationStats.customer_id == customer_id)
        )
        return result.scalar_one_or_none()
