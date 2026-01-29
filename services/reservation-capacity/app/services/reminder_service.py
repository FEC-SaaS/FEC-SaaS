"""Reservation reminder management service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import ReservationReminder, ReminderStatus
from app.schemas.reservation import ReminderCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class ReminderService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def list_reminders(self, reservation_id: UUID) -> List[ReservationReminder]:
        result = await self.db.execute(
            select(ReservationReminder)
            .where(ReservationReminder.reservation_id == reservation_id)
            .order_by(ReservationReminder.scheduled_send_time)
        )
        return list(result.scalars().all())

    async def schedule_reminder(self, reservation_id: UUID, data: ReminderCreate) -> ReservationReminder:
        reminder = ReservationReminder(
            reservation_id=reservation_id,
            reminder_type=data.reminder_type.value,
            reminder_channel=data.reminder_channel.value,
            scheduled_send_time=data.scheduled_send_time,
        )
        self.db.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)
        logger.info("reminder_scheduled", reminder_id=str(reminder.id), reservation_id=str(reservation_id))
        return reminder

    async def send_confirmation(self, reservation_id: UUID) -> Optional[ReservationReminder]:
        """Create and send a confirmation reminder via the notification service."""
        # Get reservation details for the notification
        from app.models.reservation import Reservation
        res_result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        reservation = res_result.scalar_one_or_none()

        reminder = ReservationReminder(
            reservation_id=reservation_id,
            reminder_type="CONFIRMATION",
            reminder_channel="EMAIL",
            scheduled_send_time=datetime.now(timezone.utc),
        )
        self.db.add(reminder)
        await self.db.flush()

        # Item 9: Send via notification service
        notification_id = None
        try:
            from app.services.notification_client import NotificationClient
            client = NotificationClient()
            if reservation and reservation.customer_id:
                notification_id = await client.send_reservation_confirmation(
                    customer_id=reservation.customer_id,
                    email=None,  # The notification service looks up the email
                    confirmation_code=reservation.confirmation_code,
                    reservation_date=str(reservation.reservation_date),
                    start_time=str(reservation.start_time),
                    party_size=reservation.party_size,
                )
        except Exception as e:
            logger.warning("notification_send_failed", error=str(e))
            reminder.notification_error = str(e)

        if notification_id:
            reminder.status = ReminderStatus.SENT.value
            reminder.sent_at = datetime.now(timezone.utc)
            reminder.notification_id = notification_id
        else:
            # Still mark as sent for the event, but track notification failure
            reminder.status = ReminderStatus.SENT.value
            reminder.sent_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(reminder)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.REMINDER_SENT,
                {"reminder_id": str(reminder.id), "reservation_id": str(reservation_id), "type": "CONFIRMATION"},
            )
        logger.info("confirmation_sent", reservation_id=str(reservation_id), notification_id=notification_id)
        return reminder

    async def process_pending_reminders(self) -> int:
        """Process all pending reminders that are due, sending via notification service."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ReservationReminder).where(
                ReservationReminder.status == ReminderStatus.PENDING.value,
                ReservationReminder.scheduled_send_time <= now,
            )
        )
        reminders = list(result.scalars().all())
        sent_count = 0

        from app.services.notification_client import NotificationClient
        client = NotificationClient()

        for reminder in reminders:
            # Get reservation for context
            from app.models.reservation import Reservation
            res_result = await self.db.execute(
                select(Reservation).where(Reservation.id == reminder.reservation_id)
            )
            reservation = res_result.scalar_one_or_none()

            notification_id = None
            if reservation and reservation.customer_id:
                try:
                    notification_id = await client.send_reservation_reminder(
                        customer_id=reservation.customer_id,
                        email=None,
                        confirmation_code=reservation.confirmation_code,
                        reservation_date=str(reservation.reservation_date),
                        start_time=str(reservation.start_time),
                        reminder_type=reminder.reminder_type,
                        channel=reminder.reminder_channel,
                    )
                except Exception as e:
                    logger.warning("reminder_notification_failed", error=str(e), reminder_id=str(reminder.id))
                    reminder.notification_error = str(e)

            reminder.status = ReminderStatus.SENT.value
            reminder.sent_at = now
            if notification_id:
                reminder.notification_id = notification_id
            sent_count += 1

            if self.event_publisher:
                await self.event_publisher.publish(
                    EventType.REMINDER_SENT,
                    {"reminder_id": str(reminder.id), "reservation_id": str(reminder.reservation_id)},
                )

        if sent_count > 0:
            await self.db.commit()
        logger.info("pending_reminders_processed", count=sent_count)
        return sent_count
