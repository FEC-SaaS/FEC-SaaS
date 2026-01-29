"""
=============================================================================
FILE: services/event_publisher.py
PURPOSE: Event publishing to RabbitMQ for membership events
=============================================================================
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import aio_pika
from aio_pika import Message, ExchangeType

from app.config import settings


class EventPublisher:
    """Publisher for membership-related events to RabbitMQ."""

    EXCHANGE_NAME = "membership_events"

    # Event types
    EVENT_SUBSCRIPTION_CREATED = "subscription.created"
    EVENT_SUBSCRIPTION_ACTIVATED = "subscription.activated"
    EVENT_SUBSCRIPTION_PAUSED = "subscription.paused"
    EVENT_SUBSCRIPTION_RESUMED = "subscription.resumed"
    EVENT_SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    EVENT_SUBSCRIPTION_RENEWED = "subscription.renewed"
    EVENT_SUBSCRIPTION_UPGRADED = "subscription.upgraded"
    EVENT_SUBSCRIPTION_DOWNGRADED = "subscription.downgraded"
    EVENT_SUBSCRIPTION_EXPIRED = "subscription.expired"

    EVENT_INVOICE_CREATED = "invoice.created"
    EVENT_INVOICE_PAID = "invoice.paid"
    EVENT_INVOICE_FAILED = "invoice.failed"
    EVENT_INVOICE_REFUNDED = "invoice.refunded"

    EVENT_POINTS_EARNED = "loyalty.points_earned"
    EVENT_POINTS_REDEEMED = "loyalty.points_redeemed"
    EVENT_POINTS_EXPIRED = "loyalty.points_expired"
    EVENT_POINTS_ADJUSTED = "loyalty.points_adjusted"
    EVENT_POINTS_TRANSFERRED = "loyalty.points_transferred"

    EVENT_TIER_UPGRADED = "tier.upgraded"
    EVENT_TIER_DOWNGRADED = "tier.downgraded"

    EVENT_REWARD_REDEEMED = "reward.redeemed"
    EVENT_REWARD_FULFILLED = "reward.fulfilled"
    EVENT_REWARD_CANCELLED = "reward.cancelled"

    EVENT_REFERRAL_CREATED = "referral.created"
    EVENT_REFERRAL_COMPLETED = "referral.completed"
    EVENT_REFERRAL_REWARDED = "referral.rewarded"

    EVENT_FAMILY_CREATED = "family.created"
    EVENT_FAMILY_MEMBER_ADDED = "family.member_added"
    EVENT_FAMILY_MEMBER_REMOVED = "family.member_removed"

    EVENT_CORPORATE_CREATED = "corporate.created"
    EVENT_CORPORATE_EMPLOYEE_ADDED = "corporate.employee_added"
    EVENT_CORPORATE_EMPLOYEE_REMOVED = "corporate.employee_removed"

    EVENT_DUNNING_STARTED = "dunning.started"
    EVENT_DUNNING_ATTEMPT = "dunning.attempt"
    EVENT_DUNNING_RECOVERED = "dunning.recovered"
    EVENT_DUNNING_FAILED = "dunning.failed"

    def __init__(self):
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        self.connection = await aio_pika.connect_robust(
            settings.rabbitmq_url
        )
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            self.EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()

    async def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        routing_key: Optional[str] = None,
    ) -> None:
        """Publish an event to the exchange."""
        if not self.exchange:
            await self.connect()

        # Serialize UUIDs and datetimes
        serialized_data = self._serialize_data(data)

        message_body = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "service": settings.service_name,
            "data": serialized_data,
        }

        message = Message(
            body=json.dumps(message_body).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self.exchange.publish(
            message,
            routing_key=routing_key or event_type,
        )

    def _serialize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize data for JSON encoding."""
        result = {}
        for key, value in data.items():
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = self._serialize_data(value)
            elif isinstance(value, list):
                result[key] = [
                    self._serialize_data(item) if isinstance(item, dict)
                    else str(item) if isinstance(item, (UUID, datetime))
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    # =========================================================================
    # SUBSCRIPTION EVENTS
    # =========================================================================

    async def publish_subscription_created(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        plan_id: UUID,
        venue_id: UUID,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish subscription created event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_CREATED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
                "venue_id": venue_id,
                "status": status,
                "metadata": metadata or {},
            },
        )

    async def publish_subscription_activated(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        plan_id: UUID,
    ) -> None:
        """Publish subscription activated event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_ACTIVATED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
            },
        )

    async def publish_subscription_paused(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        pause_reason: Optional[str] = None,
        scheduled_resume: Optional[datetime] = None,
    ) -> None:
        """Publish subscription paused event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_PAUSED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "pause_reason": pause_reason,
                "scheduled_resume": scheduled_resume,
            },
        )

    async def publish_subscription_resumed(
        self,
        subscription_id: UUID,
        customer_id: UUID,
    ) -> None:
        """Publish subscription resumed event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_RESUMED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
            },
        )

    async def publish_subscription_cancelled(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        cancellation_reason: Optional[str] = None,
        immediate: bool = False,
    ) -> None:
        """Publish subscription cancelled event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_CANCELLED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "cancellation_reason": cancellation_reason,
                "immediate": immediate,
            },
        )

    async def publish_subscription_renewed(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        plan_id: UUID,
        new_period_end: datetime,
    ) -> None:
        """Publish subscription renewed event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_RENEWED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
                "new_period_end": new_period_end,
            },
        )

    async def publish_subscription_upgraded(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        old_plan_id: UUID,
        new_plan_id: UUID,
    ) -> None:
        """Publish subscription upgraded event."""
        await self.publish(
            self.EVENT_SUBSCRIPTION_UPGRADED,
            {
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "old_plan_id": old_plan_id,
                "new_plan_id": new_plan_id,
            },
        )

    # =========================================================================
    # INVOICE EVENTS
    # =========================================================================

    async def publish_invoice_created(
        self,
        invoice_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        amount: float,
        currency: str,
    ) -> None:
        """Publish invoice created event."""
        await self.publish(
            self.EVENT_INVOICE_CREATED,
            {
                "invoice_id": invoice_id,
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "amount": amount,
                "currency": currency,
            },
        )

    async def publish_invoice_paid(
        self,
        invoice_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        amount: float,
        payment_intent_id: Optional[str] = None,
    ) -> None:
        """Publish invoice paid event."""
        await self.publish(
            self.EVENT_INVOICE_PAID,
            {
                "invoice_id": invoice_id,
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "amount": amount,
                "payment_intent_id": payment_intent_id,
            },
        )

    async def publish_invoice_failed(
        self,
        invoice_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        amount: float,
        failure_reason: Optional[str] = None,
    ) -> None:
        """Publish invoice failed event."""
        await self.publish(
            self.EVENT_INVOICE_FAILED,
            {
                "invoice_id": invoice_id,
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "amount": amount,
                "failure_reason": failure_reason,
            },
        )

    # =========================================================================
    # LOYALTY EVENTS
    # =========================================================================

    async def publish_points_earned(
        self,
        account_id: UUID,
        customer_id: UUID,
        points: int,
        new_balance: int,
        source: Optional[str] = None,
    ) -> None:
        """Publish points earned event."""
        await self.publish(
            self.EVENT_POINTS_EARNED,
            {
                "account_id": account_id,
                "customer_id": customer_id,
                "points_earned": points,
                "new_balance": new_balance,
                "source": source,
            },
        )

    async def publish_points_redeemed(
        self,
        account_id: UUID,
        customer_id: UUID,
        points: int,
        new_balance: int,
        redemption_type: Optional[str] = None,
    ) -> None:
        """Publish points redeemed event."""
        await self.publish(
            self.EVENT_POINTS_REDEEMED,
            {
                "account_id": account_id,
                "customer_id": customer_id,
                "points_redeemed": points,
                "new_balance": new_balance,
                "redemption_type": redemption_type,
            },
        )

    async def publish_tier_upgraded(
        self,
        account_id: UUID,
        customer_id: UUID,
        old_tier_id: Optional[UUID],
        new_tier_id: UUID,
        new_tier_name: str,
    ) -> None:
        """Publish tier upgraded event."""
        await self.publish(
            self.EVENT_TIER_UPGRADED,
            {
                "account_id": account_id,
                "customer_id": customer_id,
                "old_tier_id": old_tier_id,
                "new_tier_id": new_tier_id,
                "new_tier_name": new_tier_name,
            },
        )

    # =========================================================================
    # REWARD EVENTS
    # =========================================================================

    async def publish_reward_redeemed(
        self,
        redemption_id: UUID,
        customer_id: UUID,
        reward_id: UUID,
        reward_name: str,
        points_spent: int,
    ) -> None:
        """Publish reward redeemed event."""
        await self.publish(
            self.EVENT_REWARD_REDEEMED,
            {
                "redemption_id": redemption_id,
                "customer_id": customer_id,
                "reward_id": reward_id,
                "reward_name": reward_name,
                "points_spent": points_spent,
            },
        )

    # =========================================================================
    # REFERRAL EVENTS
    # =========================================================================

    async def publish_referral_completed(
        self,
        referral_id: UUID,
        referrer_id: UUID,
        referred_id: UUID,
        referrer_reward_points: int,
        referred_reward_points: int,
    ) -> None:
        """Publish referral completed event."""
        await self.publish(
            self.EVENT_REFERRAL_COMPLETED,
            {
                "referral_id": referral_id,
                "referrer_id": referrer_id,
                "referred_id": referred_id,
                "referrer_reward_points": referrer_reward_points,
                "referred_reward_points": referred_reward_points,
            },
        )

    # =========================================================================
    # DUNNING EVENTS
    # =========================================================================

    async def publish_dunning_started(
        self,
        dunning_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        invoice_id: UUID,
        amount: float,
    ) -> None:
        """Publish dunning started event."""
        await self.publish(
            self.EVENT_DUNNING_STARTED,
            {
                "dunning_id": dunning_id,
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "amount": amount,
            },
        )

    async def publish_dunning_recovered(
        self,
        dunning_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        recovered_amount: float,
    ) -> None:
        """Publish dunning recovered event."""
        await self.publish(
            self.EVENT_DUNNING_RECOVERED,
            {
                "dunning_id": dunning_id,
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "recovered_amount": recovered_amount,
            },
        )

    async def publish_dunning_failed(
        self,
        dunning_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        attempts_made: int,
    ) -> None:
        """Publish dunning failed event."""
        await self.publish(
            self.EVENT_DUNNING_FAILED,
            {
                "dunning_id": dunning_id,
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "attempts_made": attempts_made,
            },
        )


# Global event publisher instance
event_publisher = EventPublisher()
