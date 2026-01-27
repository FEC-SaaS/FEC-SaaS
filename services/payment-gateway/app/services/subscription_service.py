"""
=============================================================================
FILE: services/subscription_service.py
PURPOSE: Subscription management service
=============================================================================
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import (
    SubscriptionPayment,
    CustomerPaymentMethod,
    PaymentTransaction,
    BillingInterval,
    SubscriptionStatus,
    TransactionType,
    TransactionStatus,
)
from app.schemas.payment import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    PaginationParams,
)
from app.services.payment_service import PaymentService
from app.core.encryption import decrypt_sensitive_data

logger = structlog.get_logger()


class SubscriptionService:
    """Service for managing subscriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.payment_service = PaymentService(db)

    async def create_subscription(
        self,
        data: SubscriptionCreate,
        user_id: Optional[UUID] = None,
    ) -> SubscriptionResponse:
        """Create a new subscription."""
        # Validate payment method
        payment_method = await self._get_payment_method(data.payment_method_id)
        if payment_method.customer_id != data.customer_id:
            raise ValueError("Payment method does not belong to customer")

        # Get processor
        processor, config = await self.payment_service.get_processor(data.venue_id)

        # Calculate billing dates
        start_date = data.start_date or date.today()
        period_end = self._calculate_period_end(start_date, data.billing_interval)

        # Create subscription in processor
        token = decrypt_sensitive_data(payment_method.processor_token)
        result = await processor.create_subscription(
            customer_id=payment_method.processor_customer_id,
            price_amount=data.amount,
            currency=data.currency,
            interval=data.billing_interval.value,
            payment_method_token=token,
            metadata=data.metadata,
        )

        # Create subscription record
        subscription = SubscriptionPayment(
            id=uuid4(),
            customer_id=data.customer_id,
            venue_id=data.venue_id,
            membership_id=data.membership_id,
            payment_method_id=data.payment_method_id,
            config_id=config.id,
            plan_name=data.plan_name,
            billing_interval=data.billing_interval,
            amount=data.amount,
            currency=data.currency,
            status=SubscriptionStatus.ACTIVE if result.success else SubscriptionStatus.PENDING,
            start_date=start_date,
            current_period_start=start_date,
            current_period_end=period_end,
            next_billing_date=period_end,
            extra_metadata=data.metadata,
        )

        if result.success:
            subscription.processor_subscription_id = result.subscription_id
        else:
            subscription.status = SubscriptionStatus.PENDING
            logger.warning(
                "subscription_creation_partial",
                error=result.error_message,
            )

        self.db.add(subscription)
        await self.db.flush()

        logger.info(
            "subscription_created",
            subscription_id=str(subscription.id),
            customer_id=str(data.customer_id),
            amount=float(data.amount),
        )

        return SubscriptionResponse.model_validate(subscription)

    async def update_subscription(
        self,
        subscription_id: UUID,
        data: SubscriptionUpdate,
    ) -> SubscriptionResponse:
        """Update subscription details."""
        subscription = await self._get_subscription(subscription_id)

        if data.payment_method_id:
            payment_method = await self._get_payment_method(data.payment_method_id)
            if payment_method.customer_id != subscription.customer_id:
                raise ValueError("Payment method does not belong to customer")
            subscription.payment_method_id = data.payment_method_id

        if data.amount:
            subscription.amount = data.amount

        subscription.updated_at = datetime.utcnow()
        await self.db.flush()

        return SubscriptionResponse.model_validate(subscription)

    async def cancel_subscription(
        self,
        subscription_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> SubscriptionResponse:
        """Cancel a subscription."""
        subscription = await self._get_subscription(subscription_id)

        if subscription.status in [SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED]:
            raise ValueError(f"Subscription {subscription_id} is already cancelled/expired")

        # Cancel in processor
        if subscription.processor_subscription_id:
            processor, _ = await self.payment_service.get_processor(subscription.venue_id)
            result = await processor.cancel_subscription(subscription.processor_subscription_id)

            if not result.success:
                logger.warning(
                    "subscription_cancel_processor_error",
                    subscription_id=str(subscription_id),
                    error=result.error_message,
                )

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = datetime.utcnow()
        await self.db.flush()

        logger.info(
            "subscription_cancelled",
            subscription_id=str(subscription_id),
        )

        return SubscriptionResponse.model_validate(subscription)

    async def pause_subscription(
        self,
        subscription_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> SubscriptionResponse:
        """Pause a subscription."""
        subscription = await self._get_subscription(subscription_id)

        if subscription.status != SubscriptionStatus.ACTIVE:
            raise ValueError(f"Subscription {subscription_id} cannot be paused (status: {subscription.status.value})")

        # Pause in processor
        if subscription.processor_subscription_id:
            processor, _ = await self.payment_service.get_processor(subscription.venue_id)
            result = await processor.pause_subscription(subscription.processor_subscription_id)

            if not result.success:
                logger.warning(
                    "subscription_pause_processor_error",
                    subscription_id=str(subscription_id),
                    error=result.error_message,
                )

        subscription.status = SubscriptionStatus.PAUSED
        subscription.paused_at = datetime.utcnow()
        await self.db.flush()

        return SubscriptionResponse.model_validate(subscription)

    async def resume_subscription(
        self,
        subscription_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> SubscriptionResponse:
        """Resume a paused subscription."""
        subscription = await self._get_subscription(subscription_id)

        if subscription.status != SubscriptionStatus.PAUSED:
            raise ValueError(f"Subscription {subscription_id} is not paused")

        # Resume in processor
        if subscription.processor_subscription_id:
            processor, _ = await self.payment_service.get_processor(subscription.venue_id)
            result = await processor.resume_subscription(subscription.processor_subscription_id)

            if not result.success:
                logger.warning(
                    "subscription_resume_processor_error",
                    subscription_id=str(subscription_id),
                    error=result.error_message,
                )

        subscription.status = SubscriptionStatus.ACTIVE
        subscription.paused_at = None
        await self.db.flush()

        return SubscriptionResponse.model_validate(subscription)

    async def get_subscription(self, subscription_id: UUID) -> SubscriptionResponse:
        """Get subscription by ID."""
        subscription = await self._get_subscription(subscription_id)
        return SubscriptionResponse.model_validate(subscription)

    async def list_subscriptions(
        self,
        venue_id: UUID,
        customer_id: Optional[UUID] = None,
        status: Optional[SubscriptionStatus] = None,
        params: PaginationParams = PaginationParams(),
    ) -> SubscriptionListResponse:
        """List subscriptions for a venue."""
        query = select(SubscriptionPayment).where(SubscriptionPayment.venue_id == venue_id)

        if customer_id:
            query = query.where(SubscriptionPayment.customer_id == customer_id)
        if status:
            query = query.where(SubscriptionPayment.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        query = query.order_by(SubscriptionPayment.created_at.desc())
        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        result = await self.db.execute(query)
        subscriptions = result.scalars().all()

        return SubscriptionListResponse(
            subscriptions=[SubscriptionResponse.model_validate(s) for s in subscriptions],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    async def process_recurring_payment(
        self,
        subscription_id: UUID,
    ) -> Optional[PaymentTransaction]:
        """Process a recurring payment for a subscription."""
        subscription = await self._get_subscription(subscription_id)

        if subscription.status != SubscriptionStatus.ACTIVE:
            return None

        payment_method = await self._get_payment_method(subscription.payment_method_id)
        processor, config = await self.payment_service.get_processor(subscription.venue_id)

        token = decrypt_sensitive_data(payment_method.processor_token)

        # Create transaction
        transaction = PaymentTransaction(
            id=uuid4(),
            venue_id=subscription.venue_id,
            customer_id=subscription.customer_id,
            payment_method_id=subscription.payment_method_id,
            config_id=config.id,
            amount=subscription.amount,
            currency=subscription.currency,
            transaction_type=TransactionType.RECURRING,
            status=TransactionStatus.PENDING,
            description=f"Recurring payment - {subscription.plan_name}",
            subscription_id=subscription.id,
        )
        self.db.add(transaction)

        # Process payment
        result = await processor.charge(
            amount=subscription.amount,
            currency=subscription.currency,
            payment_method_token=token,
            customer_id=payment_method.processor_customer_id,
            description=f"Recurring: {subscription.plan_name}",
        )

        if result.success:
            transaction.status = TransactionStatus.COMPLETED
            transaction.processor_transaction_id = result.transaction_id
            transaction.processed_at = datetime.utcnow()

            # Update subscription billing dates
            subscription.current_period_start = subscription.current_period_end
            subscription.current_period_end = self._calculate_period_end(
                subscription.current_period_start,
                subscription.billing_interval,
            )
            subscription.next_billing_date = subscription.current_period_end
            subscription.failed_payment_count = 0
            subscription.last_payment_date = date.today()
        else:
            transaction.status = TransactionStatus.FAILED
            transaction.error_code = result.error_code
            transaction.error_message = result.error_message

            subscription.failed_payment_count += 1

            # Mark as past due if multiple failures
            if subscription.failed_payment_count >= 3:
                subscription.status = SubscriptionStatus.PAST_DUE

        await self.db.flush()

        logger.info(
            "recurring_payment_processed",
            subscription_id=str(subscription_id),
            transaction_id=str(transaction.id),
            success=result.success,
        )

        return transaction

    async def get_due_subscriptions(self) -> List[SubscriptionPayment]:
        """Get subscriptions due for billing."""
        today = date.today()
        result = await self.db.execute(
            select(SubscriptionPayment).where(
                and_(
                    SubscriptionPayment.status == SubscriptionStatus.ACTIVE,
                    SubscriptionPayment.next_billing_date <= today,
                )
            )
        )
        return list(result.scalars().all())

    async def _get_subscription(self, subscription_id: UUID) -> SubscriptionPayment:
        """Get subscription by ID."""
        result = await self.db.execute(
            select(SubscriptionPayment).where(SubscriptionPayment.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")
        return subscription

    async def _get_payment_method(self, payment_method_id: UUID) -> CustomerPaymentMethod:
        """Get payment method by ID."""
        result = await self.db.execute(
            select(CustomerPaymentMethod).where(
                CustomerPaymentMethod.id == payment_method_id,
                CustomerPaymentMethod.is_active == True,
            )
        )
        payment_method = result.scalar_one_or_none()
        if not payment_method:
            raise ValueError(f"Payment method {payment_method_id} not found")
        return payment_method

    def _calculate_period_end(
        self,
        start_date: date,
        interval: BillingInterval,
    ) -> date:
        """Calculate period end date based on billing interval."""
        if interval == BillingInterval.DAILY:
            return start_date + timedelta(days=1)
        elif interval == BillingInterval.WEEKLY:
            return start_date + timedelta(weeks=1)
        elif interval == BillingInterval.MONTHLY:
            # Add one month
            month = start_date.month + 1
            year = start_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(start_date.day, 28)  # Safe for all months
            return date(year, month, day)
        elif interval == BillingInterval.QUARTERLY:
            # Add three months
            month = start_date.month + 3
            year = start_date.year
            while month > 12:
                month -= 12
                year += 1
            day = min(start_date.day, 28)
            return date(year, month, day)
        elif interval == BillingInterval.YEARLY:
            return date(start_date.year + 1, start_date.month, start_date.day)
        else:
            return start_date + timedelta(days=30)
