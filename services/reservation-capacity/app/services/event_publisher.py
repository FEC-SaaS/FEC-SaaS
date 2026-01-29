"""RabbitMQ event publisher for reservation & capacity service."""

import enum
import json
from typing import Any, Dict, Optional
from uuid import UUID

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class EventType(str, enum.Enum):
    RESERVATION_CREATED = "reservation.created"
    RESERVATION_CONFIRMED = "reservation.confirmed"
    RESERVATION_CHECKED_IN = "reservation.checked_in"
    RESERVATION_COMPLETED = "reservation.completed"
    RESERVATION_CANCELLED = "reservation.cancelled"
    RESERVATION_NO_SHOW = "reservation.no_show"
    RESERVATION_UPDATED = "reservation.updated"
    WAITLIST_ADDED = "reservation.waitlist.added"
    WAITLIST_NOTIFIED = "reservation.waitlist.notified"
    WAITLIST_CONVERTED = "reservation.waitlist.converted"
    REMINDER_SENT = "reservation.reminder.sent"
    CAPACITY_ALERT = "reservation.capacity.alert"
    HOLD_CREATED = "reservation.hold.created"
    HOLD_EXPIRED = "reservation.hold.expired"


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


class EventPublisher:
    def __init__(self) -> None:
        self._connection = None
        self._channel = None
        self._exchange_name = "reservation_events"

    async def connect(self) -> None:
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
            )
            logger.info("event_publisher_connected")
        except Exception as e:
            logger.warning("event_publisher_connection_failed", error=str(e))
            self._connection = None
            self._channel = None

    async def disconnect(self) -> None:
        try:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
                logger.info("event_publisher_disconnected")
        except Exception as e:
            logger.warning("event_publisher_disconnect_error", error=str(e))

    async def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        venue_id: Optional[UUID] = None,
    ) -> None:
        if not self._channel:
            logger.debug("event_publisher_not_connected", event_type=event_type.value)
            return

        try:
            import aio_pika
            message = aio_pika.Message(
                body=json.dumps(
                    {"event_type": event_type.value, "venue_id": str(venue_id) if venue_id else None, "data": data},
                    cls=UUIDEncoder,
                ).encode(),
                content_type="application/json",
            )
            await self._exchange.publish(message, routing_key=event_type.value)
            logger.debug("event_published", event_type=event_type.value)
        except Exception as e:
            logger.error("event_publish_failed", event_type=event_type.value, error=str(e))


event_publisher = EventPublisher()
