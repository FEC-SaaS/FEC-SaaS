"""Core reservation management service."""

import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ErrorCode, ServiceError, conflict
from app.models.reservation import (
    DepositStatus,
    IdempotencyRecord,
    Reservation,
    ReservationItem,
    ReservationStatus,
    CustomerReservationStats,
)
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class ReservationService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    @staticmethod
    def _generate_confirmation_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(8))

    async def list_reservations(
        self,
        venue_id: UUID,
        reservation_type: Optional[str] = None,
        reservation_date=None,
        status: Optional[ReservationStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Reservation], int]:
        base_query = select(Reservation).where(Reservation.venue_id == venue_id)

        if reservation_type:
            base_query = base_query.where(Reservation.reservation_type == reservation_type)
        if reservation_date:
            base_query = base_query.where(Reservation.reservation_date == reservation_date)
        if status:
            base_query = base_query.where(Reservation.status == status.value)

        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = (
            base_query
            .order_by(Reservation.reservation_date, Reservation.start_time)
            .limit(page_size)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_reservation(self, reservation_id: UUID) -> Optional[Reservation]:
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(selectinload(Reservation.items))
        )
        return result.scalar_one_or_none()

    async def get_reservation_by_code(self, confirmation_code: str) -> Optional[Reservation]:
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.confirmation_code == confirmation_code)
            .options(selectinload(Reservation.items))
        )
        return result.scalar_one_or_none()

    async def create_reservation(
        self, venue_id: UUID, data: ReservationCreate
    ) -> Reservation:
        # Item 3: Idempotency check
        if data.idempotency_key:
            existing = await self._check_idempotency(data.idempotency_key)
            if existing:
                return existing

        # Item 2 + 10: Validation and conflict detection
        from app.services.validation_service import ValidationService
        validator = ValidationService(self.db)
        await validator.validate_reservation(venue_id, data)

        # Item 1: Rate limiting (customer-level)
        from app.core.rate_limiter import check_customer_rate
        await check_customer_rate(data.customer_id)

        deposit_status = DepositStatus.PENDING.value if data.deposit_required else DepositStatus.NOT_REQUIRED.value

        reservation = Reservation(
            venue_id=venue_id,
            customer_id=data.customer_id,
            reservation_type=data.reservation_type.value,
            reservation_date=data.reservation_date,
            start_time=data.start_time,
            end_time=data.end_time,
            party_size=data.party_size,
            status=ReservationStatus.PENDING.value,
            confirmation_code=self._generate_confirmation_code(),
            booking_channel=data.booking_channel.value if data.booking_channel else None,
            special_requests=data.special_requests,
            deposit_required=data.deposit_required,
            deposit_amount=data.deposit_amount,
            deposit_status=deposit_status,
            idempotency_key=data.idempotency_key,
        )
        self.db.add(reservation)
        await self.db.flush()

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

        # Store idempotency record
        if data.idempotency_key:
            record = IdempotencyRecord(
                idempotency_key=data.idempotency_key,
                reservation_id=reservation.id,
                response_status=201,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(reservation)

        if data.customer_id:
            await self._update_customer_stats(data.customer_id, "create")

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CREATED,
                {
                    "reservation_id": str(reservation.id),
                    "customer_id": str(data.customer_id) if data.customer_id else None,
                    "reservation_type": data.reservation_type.value,
                    "reservation_date": str(data.reservation_date),
                    "party_size": data.party_size,
                    "confirmation_code": reservation.confirmation_code,
                },
                venue_id=venue_id,
            )

        logger.info(
            "reservation_created",
            reservation_id=str(reservation.id),
            confirmation_code=reservation.confirmation_code,
        )
        return reservation

    async def update_reservation(
        self, reservation_id: UUID, data: ReservationUpdate
    ) -> Optional[Reservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status" and value is not None:
                setattr(reservation, field, value.value)
            else:
                setattr(reservation, field, value)

        await self.db.commit()
        await self.db.refresh(reservation)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_UPDATED,
                {
                    "reservation_id": str(reservation_id),
                    "updated_fields": list(update_data.keys()),
                },
                venue_id=reservation.venue_id,
            )

        logger.info("reservation_updated", reservation_id=str(reservation_id))
        return reservation

    async def _check_idempotency(self, idempotency_key: str) -> Optional[Reservation]:
        """Return existing reservation if this idempotency key was already used."""
        result = await self.db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        record = result.scalar_one_or_none()
        if record and record.reservation_id:
            existing = await self.get_reservation(record.reservation_id)
            if existing:
                logger.info(
                    "idempotency_key_reused",
                    idempotency_key=idempotency_key,
                    reservation_id=str(record.reservation_id),
                )
                return existing
        return None

    async def cancel_reservation(self, reservation_id: UUID) -> Optional[Reservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        reservation.status = ReservationStatus.CANCELLED.value
        reservation.cancelled_at = datetime.now(timezone.utc)

        # Item 8: Trigger deposit refund if collected
        if reservation.deposit_status == DepositStatus.COLLECTED.value:
            try:
                from app.services.deposit_service import DepositService
                deposit_svc = DepositService(self.db)
                await deposit_svc.refund_deposit(reservation_id, reason="cancellation")
            except Exception as e:
                logger.warning("deposit_refund_on_cancel_failed", error=str(e))

        await self.db.commit()
        await self.db.refresh(reservation)

        if reservation.customer_id:
            await self._update_customer_stats(reservation.customer_id, "cancel")

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CANCELLED,
                {"reservation_id": str(reservation_id)},
                venue_id=reservation.venue_id,
            )

        logger.info("reservation_cancelled", reservation_id=str(reservation_id))
        return reservation

    async def check_in(self, reservation_id: UUID) -> Optional[Reservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        reservation.status = ReservationStatus.CHECKED_IN.value
        reservation.checked_in_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(reservation)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CHECKED_IN,
                {"reservation_id": str(reservation_id)},
                venue_id=reservation.venue_id,
            )

        logger.info("reservation_checked_in", reservation_id=str(reservation_id))
        return reservation

    async def complete_reservation(self, reservation_id: UUID) -> Optional[Reservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        reservation.status = ReservationStatus.COMPLETED.value
        reservation.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(reservation)

        if reservation.customer_id:
            await self._update_customer_stats(reservation.customer_id, "complete")

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_COMPLETED,
                {"reservation_id": str(reservation_id)},
                venue_id=reservation.venue_id,
            )

        logger.info("reservation_completed", reservation_id=str(reservation_id))
        return reservation

    async def confirm_reservation(self, reservation_id: UUID) -> Optional[Reservation]:
        reservation = await self.get_reservation(reservation_id)
        if not reservation:
            return None

        if reservation.status != ReservationStatus.PENDING.value:
            return None

        reservation.status = ReservationStatus.CONFIRMED.value

        await self.db.commit()
        await self.db.refresh(reservation)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RESERVATION_CONFIRMED,
                {"reservation_id": str(reservation_id)},
                venue_id=reservation.venue_id,
            )

        logger.info("reservation_confirmed", reservation_id=str(reservation_id))
        return reservation

    async def _update_customer_stats(self, customer_id: UUID, action: str) -> None:
        result = await self.db.execute(
            select(CustomerReservationStats).where(
                CustomerReservationStats.customer_id == customer_id
            )
        )
        stats = result.scalar_one_or_none()

        if not stats:
            stats = CustomerReservationStats(customer_id=customer_id)
            self.db.add(stats)
            await self.db.flush()

        if action == "create":
            stats.total_reservations += 1
        elif action == "complete":
            stats.completed_reservations += 1
        elif action == "cancel":
            stats.cancelled_reservations += 1
        elif action == "no_show":
            stats.no_show_count += 1

        # Recalculate rates
        if stats.total_reservations > 0:
            stats.no_show_rate = (stats.no_show_count / stats.total_reservations) * 100
        else:
            stats.no_show_rate = 0

        reliability = 100 - (float(stats.no_show_rate) * 2)
        stats.reliability_score = max(0, min(100, reliability))

        stats.last_reservation_date = datetime.now(timezone.utc).date()
        stats.updated_at = datetime.now(timezone.utc)

        await self.db.commit()

        logger.info(
            "customer_stats_updated",
            customer_id=str(customer_id),
            action=action,
            total_reservations=stats.total_reservations,
            reliability_score=float(stats.reliability_score),
        )
