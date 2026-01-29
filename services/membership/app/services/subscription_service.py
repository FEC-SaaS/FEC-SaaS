"""
=============================================================================
FILE: services/subscription_service.py
PURPOSE: Subscription lifecycle management service
=============================================================================
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    SubscriptionPlan,
    CustomerSubscription,
    SubscriptionInvoice,
    SubscriptionUsageLimit,
    SubscriptionPause,
    DunningAttempt,
    SubscriptionStatus,
    InvoiceStatus,
    DunningStatus,
    BillingInterval,
)
from app.schemas.membership import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscribeRequest,
    SubscriptionPauseRequest,
    SubscriptionUpgradeRequest,
    SubscriptionCancelRequest,
)
from app.config import settings


class SubscriptionService:
    """Service for managing customer subscriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # SUBSCRIPTION PLANS
    # =========================================================================

    async def create_plan(
        self, venue_id: UUID, plan_data: SubscriptionPlanCreate
    ) -> SubscriptionPlan:
        """Create a new subscription plan."""
        plan = SubscriptionPlan(
            venue_id=venue_id,
            tier_id=plan_data.tier_id,
            name=plan_data.name,
            description=plan_data.description,
            billing_interval=plan_data.billing_interval,
            price=plan_data.price,
            currency=plan_data.currency,
            trial_days=plan_data.trial_days,
            features=plan_data.features or {},
            max_pauses_per_year=plan_data.max_pauses_per_year,
            max_pause_days=plan_data.max_pause_days,
            cancellation_policy=plan_data.cancellation_policy,
            is_active=True,
        )
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get_plan(self, plan_id: UUID) -> Optional[SubscriptionPlan]:
        """Get a subscription plan by ID."""
        result = await self.db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.id == plan_id)
            .options(selectinload(SubscriptionPlan.tier))
        )
        return result.scalar_one_or_none()

    async def list_plans(
        self,
        venue_id: UUID,
        tier_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> List[SubscriptionPlan]:
        """List subscription plans for a venue."""
        query = select(SubscriptionPlan).where(
            SubscriptionPlan.venue_id == venue_id
        )
        if tier_id:
            query = query.where(SubscriptionPlan.tier_id == tier_id)
        if active_only:
            query = query.where(SubscriptionPlan.is_active == True)
        query = query.order_by(SubscriptionPlan.price)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_plan(
        self, plan_id: UUID, plan_data: SubscriptionPlanUpdate
    ) -> Optional[SubscriptionPlan]:
        """Update a subscription plan."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return None

        update_data = plan_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plan, field, value)

        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def deactivate_plan(self, plan_id: UUID) -> bool:
        """Deactivate a subscription plan."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False
        plan.is_active = False
        await self.db.commit()
        return True

    # =========================================================================
    # SUBSCRIPTIONS
    # =========================================================================

    async def subscribe(
        self,
        customer_id: UUID,
        request: SubscribeRequest,
        payment_method_id: Optional[str] = None,
    ) -> CustomerSubscription:
        """Create a new subscription for a customer."""
        plan = await self.get_plan(request.plan_id)
        if not plan:
            raise ValueError("Subscription plan not found")

        # Calculate dates
        now = datetime.utcnow()
        trial_end = None
        if plan.trial_days and plan.trial_days > 0:
            trial_end = now + timedelta(days=plan.trial_days)
            next_billing = trial_end
            status = SubscriptionStatus.TRIAL
        else:
            next_billing = self._calculate_next_billing_date(
                now, plan.billing_interval
            )
            status = SubscriptionStatus.ACTIVE

        subscription = CustomerSubscription(
            customer_id=customer_id,
            plan_id=plan.id,
            status=status,
            current_period_start=now,
            current_period_end=next_billing,
            next_billing_date=next_billing,
            trial_ends_at=trial_end,
            payment_method_id=payment_method_id,
            auto_renew=request.auto_renew if request.auto_renew is not None else True,
            extra_metadata=request.metadata or {},
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        # Create initial invoice if not in trial
        if status == SubscriptionStatus.ACTIVE:
            await self._create_invoice(subscription, plan)

        return subscription

    async def get_subscription(
        self, subscription_id: UUID
    ) -> Optional[CustomerSubscription]:
        """Get a subscription by ID."""
        result = await self.db.execute(
            select(CustomerSubscription)
            .where(CustomerSubscription.id == subscription_id)
            .options(selectinload(CustomerSubscription.plan))
        )
        return result.scalar_one_or_none()

    async def get_customer_subscriptions(
        self,
        customer_id: UUID,
        active_only: bool = False,
    ) -> List[CustomerSubscription]:
        """Get all subscriptions for a customer."""
        query = select(CustomerSubscription).where(
            CustomerSubscription.customer_id == customer_id
        )
        if active_only:
            query = query.where(
                CustomerSubscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                ])
            )
        query = query.options(selectinload(CustomerSubscription.plan))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def pause_subscription(
        self,
        subscription_id: UUID,
        request: SubscriptionPauseRequest,
    ) -> Optional[SubscriptionPause]:
        """Pause a subscription."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            return None

        if subscription.status not in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIAL,
        ]:
            raise ValueError("Can only pause active subscriptions")

        # Check pause limits
        plan = await self.get_plan(subscription.plan_id)
        if plan.max_pauses_per_year:
            year_start = datetime.utcnow().replace(
                month=1, day=1, hour=0, minute=0, second=0
            )
            pauses_this_year = await self._count_pauses(
                subscription_id, since=year_start
            )
            if pauses_this_year >= plan.max_pauses_per_year:
                raise ValueError("Maximum pauses per year exceeded")

        # Calculate pause duration
        pause_days = (request.resume_date - datetime.utcnow()).days
        max_days = plan.max_pause_days or settings.max_pause_days
        if pause_days > max_days:
            raise ValueError(f"Maximum pause duration is {max_days} days")

        # Create pause record
        pause = SubscriptionPause(
            subscription_id=subscription_id,
            pause_start=datetime.utcnow(),
            scheduled_resume=request.resume_date,
            reason=request.reason,
        )
        self.db.add(pause)

        # Update subscription status
        subscription.status = SubscriptionStatus.PAUSED
        subscription.paused_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(pause)
        return pause

    async def resume_subscription(
        self, subscription_id: UUID
    ) -> Optional[CustomerSubscription]:
        """Resume a paused subscription."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            return None

        if subscription.status != SubscriptionStatus.PAUSED:
            raise ValueError("Subscription is not paused")

        # Find active pause and end it
        result = await self.db.execute(
            select(SubscriptionPause)
            .where(
                and_(
                    SubscriptionPause.subscription_id == subscription_id,
                    SubscriptionPause.actual_resume.is_(None),
                )
            )
            .order_by(SubscriptionPause.pause_start.desc())
            .limit(1)
        )
        pause = result.scalar_one_or_none()
        if pause:
            pause.actual_resume = datetime.utcnow()

        # Calculate billing extension based on pause duration
        if subscription.paused_at:
            pause_days = (datetime.utcnow() - subscription.paused_at).days
            subscription.next_billing_date += timedelta(days=pause_days)
            subscription.current_period_end += timedelta(days=pause_days)

        subscription.status = SubscriptionStatus.ACTIVE
        subscription.paused_at = None

        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def cancel_subscription(
        self,
        subscription_id: UUID,
        request: SubscriptionCancelRequest,
    ) -> Optional[CustomerSubscription]:
        """Cancel a subscription."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            return None

        subscription.cancellation_reason = request.reason
        subscription.cancelled_at = datetime.utcnow()

        if request.immediate:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.ended_at = datetime.utcnow()
        else:
            # Cancel at end of billing period
            subscription.status = SubscriptionStatus.PENDING_CANCELLATION
            subscription.auto_renew = False

        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def upgrade_downgrade(
        self,
        subscription_id: UUID,
        request: SubscriptionUpgradeRequest,
    ) -> Optional[CustomerSubscription]:
        """Upgrade or downgrade a subscription to a new plan."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            return None

        new_plan = await self.get_plan(request.new_plan_id)
        if not new_plan:
            raise ValueError("New plan not found")

        old_plan = await self.get_plan(subscription.plan_id)

        if request.immediate:
            # Calculate proration
            if request.prorate:
                days_remaining = (
                    subscription.current_period_end - datetime.utcnow()
                ).days
                total_days = (
                    subscription.current_period_end
                    - subscription.current_period_start
                ).days
                if total_days > 0:
                    proration_factor = Decimal(days_remaining) / Decimal(
                        total_days
                    )
                    credit = old_plan.price * proration_factor
                    charge = new_plan.price * proration_factor
                    # Net charge/credit would be handled by payment service

            subscription.plan_id = new_plan.id
            subscription.current_period_start = datetime.utcnow()
            subscription.current_period_end = self._calculate_next_billing_date(
                datetime.utcnow(), new_plan.billing_interval
            )
            subscription.next_billing_date = subscription.current_period_end
        else:
            # Schedule change for next billing cycle
            subscription.extra_metadata = subscription.extra_metadata or {}
            subscription.extra_metadata["pending_plan_change"] = str(new_plan.id)

        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    # =========================================================================
    # BILLING & INVOICES
    # =========================================================================

    async def _create_invoice(
        self,
        subscription: CustomerSubscription,
        plan: SubscriptionPlan,
    ) -> SubscriptionInvoice:
        """Create an invoice for a subscription."""
        invoice = SubscriptionInvoice(
            subscription_id=subscription.id,
            amount=plan.price,
            currency=plan.currency,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            status=InvoiceStatus.PENDING,
            due_date=datetime.utcnow() + timedelta(days=7),
        )
        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def process_invoice_payment(
        self,
        invoice_id: UUID,
        payment_intent_id: str,
        success: bool,
    ) -> SubscriptionInvoice:
        """Process payment for an invoice."""
        result = await self.db.execute(
            select(SubscriptionInvoice).where(
                SubscriptionInvoice.id == invoice_id
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise ValueError("Invoice not found")

        if success:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.utcnow()
            invoice.payment_intent_id = payment_intent_id
        else:
            invoice.status = InvoiceStatus.FAILED
            # Initialize dunning process
            await self._start_dunning(invoice)

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def _start_dunning(self, invoice: SubscriptionInvoice) -> None:
        """Start the dunning process for a failed payment."""
        dunning = DunningAttempt(
            subscription_id=invoice.subscription_id,
            invoice_id=invoice.id,
            attempt_number=1,
            amount=invoice.amount,
            status=DunningStatus.PENDING,
            next_attempt_at=datetime.utcnow()
            + timedelta(days=settings.dunning_retry_days[0]),
        )
        self.db.add(dunning)

    async def process_dunning_attempt(
        self, dunning_id: UUID, success: bool
    ) -> DunningAttempt:
        """Process a dunning retry attempt."""
        result = await self.db.execute(
            select(DunningAttempt).where(DunningAttempt.id == dunning_id)
        )
        dunning = result.scalar_one_or_none()
        if not dunning:
            raise ValueError("Dunning attempt not found")

        dunning.attempted_at = datetime.utcnow()

        if success:
            dunning.status = DunningStatus.RECOVERED
            dunning.recovered_at = datetime.utcnow()
            # Mark invoice as paid
            invoice_result = await self.db.execute(
                select(SubscriptionInvoice).where(
                    SubscriptionInvoice.id == dunning.invoice_id
                )
            )
            invoice = invoice_result.scalar_one()
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.utcnow()
        else:
            if dunning.attempt_number >= settings.dunning_max_attempts:
                dunning.status = DunningStatus.FAILED
                # Cancel subscription due to payment failure
                subscription = await self.get_subscription(
                    dunning.subscription_id
                )
                if subscription:
                    subscription.status = SubscriptionStatus.PAST_DUE
            else:
                # Schedule next attempt
                next_attempt_idx = min(
                    dunning.attempt_number,
                    len(settings.dunning_retry_days) - 1,
                )
                dunning.next_attempt_at = datetime.utcnow() + timedelta(
                    days=settings.dunning_retry_days[next_attempt_idx]
                )
                # Create next dunning attempt
                next_dunning = DunningAttempt(
                    subscription_id=dunning.subscription_id,
                    invoice_id=dunning.invoice_id,
                    attempt_number=dunning.attempt_number + 1,
                    amount=dunning.amount,
                    status=DunningStatus.PENDING,
                    next_attempt_at=dunning.next_attempt_at,
                )
                self.db.add(next_dunning)
                dunning.status = DunningStatus.FAILED

        await self.db.commit()
        await self.db.refresh(dunning)
        return dunning

    # =========================================================================
    # USAGE TRACKING
    # =========================================================================

    async def create_usage_limit(
        self,
        plan_id: UUID,
        usage_type: str,
        limit_value: int,
        reset_period: str,
    ) -> SubscriptionUsageLimit:
        """Create a usage limit for a plan."""
        usage_limit = SubscriptionUsageLimit(
            plan_id=plan_id,
            usage_type=usage_type,
            limit_value=limit_value,
            reset_period=reset_period,
        )
        self.db.add(usage_limit)
        await self.db.commit()
        await self.db.refresh(usage_limit)
        return usage_limit

    async def get_usage_limits(
        self, plan_id: UUID
    ) -> List[SubscriptionUsageLimit]:
        """Get all usage limits for a plan."""
        result = await self.db.execute(
            select(SubscriptionUsageLimit).where(
                SubscriptionUsageLimit.plan_id == plan_id
            )
        )
        return list(result.scalars().all())

    async def track_usage(
        self,
        subscription_id: UUID,
        usage_type: str,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Track usage for a subscription."""
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise ValueError("Subscription not found")

        # Get usage limit for this type
        result = await self.db.execute(
            select(SubscriptionUsageLimit).where(
                and_(
                    SubscriptionUsageLimit.plan_id == subscription.plan_id,
                    SubscriptionUsageLimit.usage_type == usage_type,
                )
            )
        )
        limit = result.scalar_one_or_none()

        # Track in metadata
        subscription.extra_metadata = subscription.extra_metadata or {}
        usage_key = f"usage_{usage_type}"
        current_usage = subscription.extra_metadata.get(usage_key, 0)
        new_usage = current_usage + quantity
        subscription.extra_metadata[usage_key] = new_usage

        await self.db.commit()

        return {
            "usage_type": usage_type,
            "current_usage": new_usage,
            "limit": limit.limit_value if limit else None,
            "remaining": (limit.limit_value - new_usage) if limit else None,
            "exceeded": (new_usage > limit.limit_value) if limit else False,
        }

    # =========================================================================
    # RENEWALS
    # =========================================================================

    async def process_renewals(self) -> List[CustomerSubscription]:
        """Process all subscriptions due for renewal."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(CustomerSubscription)
            .where(
                and_(
                    CustomerSubscription.status == SubscriptionStatus.ACTIVE,
                    CustomerSubscription.auto_renew == True,
                    CustomerSubscription.next_billing_date <= now,
                )
            )
            .options(selectinload(CustomerSubscription.plan))
        )
        subscriptions = list(result.scalars().all())

        renewed = []
        for subscription in subscriptions:
            try:
                plan = subscription.plan
                # Create new invoice
                subscription.current_period_start = now
                subscription.current_period_end = (
                    self._calculate_next_billing_date(now, plan.billing_interval)
                )
                subscription.next_billing_date = subscription.current_period_end

                await self._create_invoice(subscription, plan)
                renewed.append(subscription)
            except Exception:
                # Log error but continue with other subscriptions
                pass

        await self.db.commit()
        return renewed

    async def convert_trials(self) -> List[CustomerSubscription]:
        """Convert expired trials to active subscriptions."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(CustomerSubscription)
            .where(
                and_(
                    CustomerSubscription.status == SubscriptionStatus.TRIAL,
                    CustomerSubscription.trial_ends_at <= now,
                )
            )
            .options(selectinload(CustomerSubscription.plan))
        )
        subscriptions = list(result.scalars().all())

        converted = []
        for subscription in subscriptions:
            try:
                plan = subscription.plan
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.current_period_start = now
                subscription.current_period_end = (
                    self._calculate_next_billing_date(now, plan.billing_interval)
                )
                subscription.next_billing_date = subscription.current_period_end

                await self._create_invoice(subscription, plan)
                converted.append(subscription)
            except Exception:
                pass

        await self.db.commit()
        return converted

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _calculate_next_billing_date(
        self, from_date: datetime, interval: BillingInterval
    ) -> datetime:
        """Calculate the next billing date based on interval."""
        if interval == BillingInterval.WEEKLY:
            return from_date + timedelta(days=7)
        elif interval == BillingInterval.MONTHLY:
            # Add roughly a month
            return from_date + timedelta(days=30)
        elif interval == BillingInterval.QUARTERLY:
            return from_date + timedelta(days=90)
        elif interval == BillingInterval.SEMI_ANNUAL:
            return from_date + timedelta(days=180)
        elif interval == BillingInterval.ANNUAL:
            return from_date + timedelta(days=365)
        else:
            return from_date + timedelta(days=30)

    async def _count_pauses(
        self, subscription_id: UUID, since: datetime
    ) -> int:
        """Count pauses for a subscription since a given date."""
        result = await self.db.execute(
            select(func.count(SubscriptionPause.id)).where(
                and_(
                    SubscriptionPause.subscription_id == subscription_id,
                    SubscriptionPause.pause_start >= since,
                )
            )
        )
        return result.scalar() or 0
