"""Group and block reservation management service."""

import uuid as uuid_module
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, bad_request, conflict
from app.models.reservation import (
    Reservation,
    ReservationItem,
    ReservationStatus,
    CapacityConfig,
)
from app.schemas.reservation import GroupBookingCreate
from app.services.event_publisher import EventPublisher, EventType
from app.services.reservation_service import ReservationService

logger = structlog.get_logger()


class GroupBookingService:
    """Manages group/block reservations for corporate events, leagues, etc."""

    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher
        self._reservation_service = ReservationService(db, event_publisher)

    async def create_group_booking(
        self, venue_id: UUID, data: GroupBookingCreate
    ) -> List[Reservation]:
        """Create a group/block booking with multiple resource reservations."""
        # Validate total resource count against capacity
        await self._validate_group_capacity(venue_id, data)

        group_id = uuid_module.uuid4()
        created: List[Reservation] = []

        for resource_block in data.resource_blocks:
            reservation = Reservation(
                venue_id=venue_id,
                customer_id=data.customer_id,
                reservation_type=data.reservation_type.value,
                reservation_date=data.reservation_date,
                start_time=data.start_time,
                end_time=data.end_time,
                party_size=resource_block.party_size,
                status=ReservationStatus.PENDING.value,
                confirmation_code=self._reservation_service._generate_confirmation_code(),
                booking_channel=data.booking_channel.value if data.booking_channel else None,
                special_requests=data.special_requests,
                deposit_required=data.deposit_required,
                deposit_amount=data.deposit_amount,
                is_group_booking=True,
                group_booking_id=group_id,
                group_name=data.group_name,
                group_contact_name=data.group_contact_name,
                group_contact_email=data.group_contact_email,
                group_contact_phone=data.group_contact_phone,
            )
            self.db.add(reservation)
            await self.db.flush()

            # Add items for this resource block
            item = ReservationItem(
                reservation_id=reservation.id,
                item_type=resource_block.resource_type.value,
                item_id=resource_block.resource_id,
                quantity=resource_block.quantity,
                duration_minutes=resource_block.duration_minutes,
                base_price=resource_block.base_price,
                assigned_resource_id=resource_block.resource_id,
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
                    "type": "group_booking",
                    "group_booking_id": str(group_id),
                    "group_name": data.group_name,
                    "total_resources": len(data.resource_blocks),
                    "total_party_size": sum(rb.party_size for rb in data.resource_blocks),
                },
                venue_id=venue_id,
            )

        logger.info(
            "group_booking_created",
            group_id=str(group_id),
            group_name=data.group_name,
            resource_count=len(created),
        )
        return created

    async def get_group(self, group_booking_id: UUID) -> List[Reservation]:
        """Get all reservations in a group booking."""
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.group_booking_id == group_booking_id)
            .order_by(Reservation.start_time)
        )
        return list(result.scalars().all())

    async def cancel_group(self, group_booking_id: UUID) -> List[Reservation]:
        """Cancel all reservations in a group booking."""
        result = await self.db.execute(
            select(Reservation).where(
                and_(
                    Reservation.group_booking_id == group_booking_id,
                    Reservation.status.in_([
                        ReservationStatus.PENDING.value,
                        ReservationStatus.CONFIRMED.value,
                    ]),
                )
            )
        )
        reservations = list(result.scalars().all())
        now = datetime.now(timezone.utc)

        for res in reservations:
            res.status = ReservationStatus.CANCELLED.value
            res.cancelled_at = now

        await self.db.commit()
        for res in reservations:
            await self.db.refresh(res)

        logger.info(
            "group_booking_cancelled",
            group_id=str(group_booking_id),
            count=len(reservations),
        )
        return reservations

    async def _validate_group_capacity(
        self, venue_id: UUID, data: GroupBookingCreate
    ) -> None:
        """Verify the venue has enough capacity for the group booking."""
        for block in data.resource_blocks:
            result = await self.db.execute(
                select(CapacityConfig).where(
                    and_(
                        CapacityConfig.venue_id == venue_id,
                        CapacityConfig.resource_type == block.resource_type.value,
                    )
                )
            )
            config = result.scalar_one_or_none()
            if config and block.quantity > config.total_capacity:
                raise bad_request(
                    ErrorCode.GROUP_INSUFFICIENT_RESOURCES,
                    f"Requested {block.quantity} {block.resource_type.value} but venue only has {config.total_capacity}.",
                    {
                        "resource_type": block.resource_type.value,
                        "requested": block.quantity,
                        "available": config.total_capacity,
                    },
                )

        total_party = sum(rb.party_size for rb in data.resource_blocks)
        if total_party > 500:
            raise bad_request(
                ErrorCode.GROUP_SIZE_EXCEEDED,
                f"Total group size ({total_party}) exceeds maximum of 500.",
                {"total_party_size": total_party, "max": 500},
            )
