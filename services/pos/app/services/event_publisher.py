"""RabbitMQ event publisher for POS Integration service."""

import enum
import json
from typing import Any, Dict, Optional
from uuid import UUID

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class EventType(str, enum.Enum):
    # Transaction events
    TRANSACTION_CREATED = "pos.transaction.created"
    TRANSACTION_COMPLETED = "pos.transaction.completed"
    TRANSACTION_VOIDED = "pos.transaction.voided"

    # Payment events
    PAYMENT_PROCESSED = "pos.payment.processed"
    PAYMENT_REVERSED = "pos.payment.reversed"
    PAYMENT_FAILED = "pos.payment.failed"

    # Receipt events
    RECEIPT_GENERATED = "pos.receipt.generated"
    RECEIPT_EMAILED = "pos.receipt.emailed"

    # Refund events
    REFUND_ISSUED = "pos.refund.issued"
    REFUND_APPROVED = "pos.refund.approved"

    # Cash drawer events
    DRAWER_OPENED = "pos.drawer.opened"
    DRAWER_CLOSED = "pos.drawer.closed"
    DRAWER_CASH_DROP = "pos.drawer.cash_drop"
    DRAWER_VARIANCE_ALERT = "pos.drawer.variance_alert"

    # Reconciliation events
    RECONCILIATION_CREATED = "pos.reconciliation.created"
    RECONCILIATION_COMPLETED = "pos.reconciliation.completed"
    RECONCILIATION_DISCREPANCY = "pos.reconciliation.discrepancy"

    # External POS events
    POS_SYNC_COMPLETED = "pos.sync.completed"
    POS_SYNC_FAILED = "pos.sync.failed"

    # Analytics events
    DAILY_SALES_SUMMARY = "pos.analytics.daily_sales"

    # Tip pool events
    TIP_POOL_CREATED = "pos.tip_pool.created"
    TIP_POOL_CLOSED = "pos.tip_pool.closed"
    TIP_POOL_DISTRIBUTED = "pos.tip_pool.distributed"
    TIP_POOL_PARTICIPANT_ADDED = "pos.tip_pool.participant_added"
    TIP_POOL_TIPS_ADDED = "pos.tip_pool.tips_added"

    # Fraud detection events
    FRAUD_ALERT_CREATED = "pos.fraud.alert_created"
    FRAUD_ALERT_ESCALATED = "pos.fraud.alert_escalated"
    FRAUD_ALERT_RESOLVED = "pos.fraud.alert_resolved"

    # Inventory deduction events (for inventory service to consume)
    INVENTORY_DEDUCT = "pos.inventory.deduct"
    INVENTORY_RESTORE = "pos.inventory.restore"  # On void/refund
    INVENTORY_ADJUSTMENT = "pos.inventory.adjustment"

    # Discount events
    DISCOUNT_CREATED = "pos.discount.created"
    DISCOUNT_APPLIED = "pos.discount.applied"
    DISCOUNT_DEACTIVATED = "pos.discount.deactivated"

    # Shift events
    SHIFT_CREATED = "pos.shift.created"
    SHIFT_STARTED = "pos.shift.started"
    SHIFT_ENDED = "pos.shift.ended"
    SHIFT_CANCELLED = "pos.shift.cancelled"

    # Currency events
    CURRENCY_RATE_UPDATED = "pos.currency.rate_updated"


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


class EventPublisher:
    def __init__(self) -> None:
        self._connection = None
        self._channel = None
        self._exchange_name = "pos_events"

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
                    {
                        "event_type": event_type.value,
                        "venue_id": str(venue_id) if venue_id else None,
                        "data": data,
                    },
                    cls=UUIDEncoder,
                ).encode(),
                content_type="application/json",
            )
            await self._exchange.publish(message, routing_key=event_type.value)
            logger.debug("event_published", event_type=event_type.value)
        except Exception as e:
            logger.error("event_publish_failed", event_type=event_type.value, error=str(e))


event_publisher = EventPublisher()
