"""
=============================================================================
FILE: services/event_publisher.py
PURPOSE: Event publishing for payment events
=============================================================================
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

import structlog
import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode

from app.config import settings

logger = structlog.get_logger()


class EventType(str, Enum):
    """Payment event types."""
    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_DECLINED = "payment.declined"
    PAYMENT_VOIDED = "payment.voided"
    PAYMENT_AUTHORIZED = "payment.authorized"
    PAYMENT_CAPTURED = "payment.captured"

    # Refund events
    REFUND_INITIATED = "refund.initiated"
    REFUND_COMPLETED = "refund.completed"
    REFUND_FAILED = "refund.failed"

    # Subscription events
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_ACTIVATED = "subscription.activated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SUBSCRIPTION_PAUSED = "subscription.paused"
    SUBSCRIPTION_RESUMED = "subscription.resumed"
    SUBSCRIPTION_RENEWED = "subscription.renewed"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription.payment_failed"
    SUBSCRIPTION_EXPIRED = "subscription.expired"

    # Payment method events
    PAYMENT_METHOD_ADDED = "payment_method.added"
    PAYMENT_METHOD_REMOVED = "payment_method.removed"
    PAYMENT_METHOD_UPDATED = "payment_method.updated"
    PAYMENT_METHOD_EXPIRED = "payment_method.expired"

    # Fraud events
    FRAUD_ALERT_CREATED = "fraud.alert_created"
    FRAUD_ALERT_REVIEWED = "fraud.alert_reviewed"
    FRAUD_TRANSACTION_BLOCKED = "fraud.transaction_blocked"

    # Dispute events
    DISPUTE_CREATED = "dispute.created"
    DISPUTE_EVIDENCE_SUBMITTED = "dispute.evidence_submitted"
    DISPUTE_WON = "dispute.won"
    DISPUTE_LOST = "dispute.lost"
    DISPUTE_CLOSED = "dispute.closed"


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and UUID types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class EventPublisher:
    """Publisher for payment events to message broker."""

    def __init__(self):
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._exchange: Optional[aio_pika.Exchange] = None
        self._exchange_name = "payment_events"

    async def connect(self) -> None:
        """Establish connection to message broker."""
        if self._connection is None or self._connection.is_closed:
            self._connection = await aio_pika.connect_robust(
                settings.rabbitmq_url,
            )
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
            logger.info("event_publisher_connected", exchange=self._exchange_name)

    async def disconnect(self) -> None:
        """Close connection to message broker."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("event_publisher_disconnected")

    async def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        venue_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Publish an event to the message broker."""
        await self.connect()

        event = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "payment-gateway",
            "payload": payload,
        }

        if venue_id:
            event["venue_id"] = str(venue_id)
        if correlation_id:
            event["correlation_id"] = correlation_id

        message = Message(
            body=json.dumps(event, cls=DecimalEncoder).encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            headers={
                "event_type": event_type.value,
                "source": "payment-gateway",
            },
        )

        routing_key = f"payment.{event_type.value}"

        await self._exchange.publish(message, routing_key=routing_key)

        logger.info(
            "event_published",
            event_type=event_type.value,
            routing_key=routing_key,
        )

    async def publish_payment_completed(
        self,
        transaction_id: UUID,
        venue_id: UUID,
        customer_id: Optional[UUID],
        amount: Decimal,
        currency: str,
        payment_method_id: Optional[UUID] = None,
        order_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish payment completed event."""
        await self.publish(
            EventType.PAYMENT_COMPLETED,
            payload={
                "transaction_id": transaction_id,
                "customer_id": customer_id,
                "payment_method_id": payment_method_id,
                "amount": amount,
                "currency": currency,
                "order_id": order_id,
                "metadata": metadata,
            },
            venue_id=venue_id,
        )

    async def publish_payment_failed(
        self,
        transaction_id: UUID,
        venue_id: UUID,
        customer_id: Optional[UUID],
        amount: Decimal,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Publish payment failed event."""
        await self.publish(
            EventType.PAYMENT_FAILED,
            payload={
                "transaction_id": transaction_id,
                "customer_id": customer_id,
                "amount": amount,
                "error_code": error_code,
                "error_message": error_message,
            },
            venue_id=venue_id,
        )

    async def publish_refund_completed(
        self,
        refund_id: UUID,
        transaction_id: UUID,
        venue_id: UUID,
        customer_id: Optional[UUID],
        amount: Decimal,
    ) -> None:
        """Publish refund completed event."""
        await self.publish(
            EventType.REFUND_COMPLETED,
            payload={
                "refund_id": refund_id,
                "transaction_id": transaction_id,
                "customer_id": customer_id,
                "amount": amount,
            },
            venue_id=venue_id,
        )

    async def publish_subscription_created(
        self,
        subscription_id: UUID,
        venue_id: UUID,
        customer_id: UUID,
        plan_name: str,
        amount: Decimal,
        interval: str,
    ) -> None:
        """Publish subscription created event."""
        await self.publish(
            EventType.SUBSCRIPTION_CREATED,
            payload={
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "plan_name": plan_name,
                "amount": amount,
                "interval": interval,
            },
            venue_id=venue_id,
        )

    async def publish_subscription_cancelled(
        self,
        subscription_id: UUID,
        venue_id: UUID,
        customer_id: UUID,
    ) -> None:
        """Publish subscription cancelled event."""
        await self.publish(
            EventType.SUBSCRIPTION_CANCELLED,
            payload={
                "subscription_id": subscription_id,
                "customer_id": customer_id,
            },
            venue_id=venue_id,
        )

    async def publish_fraud_alert(
        self,
        alert_id: UUID,
        transaction_id: UUID,
        venue_id: UUID,
        fraud_score: Decimal,
        risk_level: str,
        triggered_rules: list,
    ) -> None:
        """Publish fraud alert event."""
        await self.publish(
            EventType.FRAUD_ALERT_CREATED,
            payload={
                "alert_id": alert_id,
                "transaction_id": transaction_id,
                "fraud_score": fraud_score,
                "risk_level": risk_level,
                "triggered_rules": triggered_rules,
            },
            venue_id=venue_id,
        )

    async def publish_dispute_created(
        self,
        dispute_id: UUID,
        transaction_id: UUID,
        venue_id: UUID,
        dispute_amount: Decimal,
        dispute_type: str,
    ) -> None:
        """Publish dispute created event."""
        await self.publish(
            EventType.DISPUTE_CREATED,
            payload={
                "dispute_id": dispute_id,
                "transaction_id": transaction_id,
                "dispute_amount": dispute_amount,
                "dispute_type": dispute_type,
            },
            venue_id=venue_id,
        )


# Global instance
event_publisher = EventPublisher()
