"""Reservation management service."""

from datetime import date, datetime, time, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import (
    DiningTable,
    ReservationStatus,
    TableReservation,
    TableStatus,
)
from app.schemas.restaurant import ReservationCreate, ReservationSeat
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class ReservationService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def list_reservations(
        self,
        venue_id: UUID,
        reservation_date: Optional[date] = None,
        status: Optional[ReservationStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[TableReservation], int]:
        base_query = select(TableReservation).where(TableReservation.venue_id == venue_id)
        if reservation_date:
            base_query = base_query.where(TableReservation.reservation_date == reservation_date)
        if status:
            base_query = base_query.where(TableReservation.status == status.value)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = (
            base_query
            .order_by(TableReservation.reservation_date, TableReservation.reservation_time)
            .limit(page_size)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_reservation(self, reservation_id: UUID) -> Optional[TableReservation]:
        result = await self.db.execute(
            select(TableReservation).where(TableReservation.id == reservation_id)
        )
        return result.scalar_one_or_none()

    async def create_reservation(self, venue_id: UUID, data: ReservationCreate) -> TableReservation:
        reservation = TableReservation(
            venue_id=venue_id,
            customer_id=data.customer_id,
            table_id=data.table_id,
            reservation_date=data.reservation_date,
            reservation_time=data.reservation_time,
            party_size=data.party_size,
            special_requests=data.special_requests,
            status=ReservationStatus.CONFIRMED.value,
        )
        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CREATED,
                {
                    "reservation_id": str(reservation.id),
                    "customer_id": str(data.customer_id) if data.customer_id else None,
                    "reservation_date": str(data.reservation_date),
                    "party_size": data.party_size,
                },
                venue_id=venue_id,
            )
        logger.info("reservation_created", reservation_id=str(reservation.id))
        return reservation

    async def seat_reservation(self, reservation_id: UUID, data: ReservationSeat) -> Optional[TableReservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        reservation.status = ReservationStatus.SEATED.value
        reservation.seated_at = datetime.now(timezone.utc)

        if data.table_id:
            reservation.table_id = data.table_id

        # Update table status to occupied
        if reservation.table_id:
            table_result = await self.db.execute(
                select(DiningTable).where(DiningTable.id == reservation.table_id)
            )
            table = table_result.scalar_one_or_none()
            if table:
                table.status = TableStatus.OCCUPIED.value

        await self.db.commit()
        await self.db.refresh(reservation)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_SEATED,
                {"reservation_id": str(reservation_id), "table_id": str(reservation.table_id)},
                venue_id=reservation.venue_id,
            )
        logger.info("reservation_seated", reservation_id=str(reservation_id))
        return reservation

    async def cancel_reservation(self, reservation_id: UUID) -> Optional[TableReservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        reservation.status = ReservationStatus.CANCELLED.value
        await self.db.commit()
        await self.db.refresh(reservation)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CANCELLED,
                {"reservation_id": str(reservation_id)},
                venue_id=reservation.venue_id,
            )
        logger.info("reservation_cancelled", reservation_id=str(reservation_id))
        return reservation
