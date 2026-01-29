"""
=============================================================================
FILE: tests/test_subscriptions.py
PURPOSE: Tests for subscription management functionality
=============================================================================
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SubscriptionPlan,
    CustomerSubscription,
    MembershipTier,
    SubscriptionStatus,
    BillingInterval,
)
from app.services import SubscriptionService
from app.schemas.membership import (
    SubscriptionPlanCreate,
    SubscribeRequest,
    PauseSubscriptionRequest,
    CancelSubscriptionRequest,
)


class TestSubscriptionPlanCRUD:
    """Tests for subscription plan CRUD operations."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> SubscriptionService:
        return SubscriptionService(db_session)

    @pytest_asyncio.fixture
    async def venue_id(self) -> str:
        return uuid4()

    async def test_create_subscription_plan(
        self, service: SubscriptionService, venue_id, sample_subscription_plan_data
    ):
        """Test creating a subscription plan."""
        plan_data = SubscriptionPlanCreate(**sample_subscription_plan_data)
        plan = await service.create_plan(venue_id, plan_data)

        assert plan is not None
        assert plan.name == sample_subscription_plan_data["name"]
        assert plan.price == Decimal(sample_subscription_plan_data["price"])
        assert plan.billing_interval == BillingInterval.MONTHLY
        assert plan.is_active is True

    async def test_get_subscription_plan(
        self, service: SubscriptionService, venue_id, sample_subscription_plan_data
    ):
        """Test retrieving a subscription plan."""
        plan_data = SubscriptionPlanCreate(**sample_subscription_plan_data)
        created = await service.create_plan(venue_id, plan_data)

        retrieved = await service.get_plan(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    async def test_list_subscription_plans(
        self, service: SubscriptionService, venue_id, sample_subscription_plan_data
    ):
        """Test listing subscription plans."""
        # Create multiple plans
        for i in range(3):
            data = sample_subscription_plan_data.copy()
            data["name"] = f"Plan {i}"
            data["price"] = str(10.0 * (i + 1))
            plan_data = SubscriptionPlanCreate(**data)
            await service.create_plan(venue_id, plan_data)

        plans = await service.list_plans(venue_id)

        assert len(plans) == 3
        # Should be ordered by price
        assert plans[0].price < plans[1].price < plans[2].price

    async def test_deactivate_subscription_plan(
        self, service: SubscriptionService, venue_id, sample_subscription_plan_data
    ):
        """Test deactivating a subscription plan."""
        plan_data = SubscriptionPlanCreate(**sample_subscription_plan_data)
        plan = await service.create_plan(venue_id, plan_data)

        result = await service.deactivate_plan(plan.id)

        assert result is True
        updated = await service.get_plan(plan.id)
        assert updated.is_active is False


class TestCustomerSubscriptions:
    """Tests for customer subscription operations."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> SubscriptionService:
        return SubscriptionService(db_session)

    @pytest_asyncio.fixture
    async def subscription_plan(
        self, db_session: AsyncSession, sample_subscription_plan_data
    ) -> SubscriptionPlan:
        """Create a test subscription plan."""
        venue_id = uuid4()
        plan = SubscriptionPlan(
            venue_id=venue_id,
            name=sample_subscription_plan_data["name"],
            description=sample_subscription_plan_data["description"],
            billing_interval=BillingInterval.MONTHLY,
            price=Decimal(sample_subscription_plan_data["price"]),
            currency="USD",
            trial_days=14,
            features=sample_subscription_plan_data["features"],
            max_pauses_per_year=2,
            max_pause_days=30,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    async def test_subscribe_with_trial(
        self, service: SubscriptionService, subscription_plan: SubscriptionPlan
    ):
        """Test subscribing to a plan with a trial period."""
        customer_id = uuid4()
        request = SubscribeRequest(
            plan_id=subscription_plan.id,
            auto_renew=True,
        )

        subscription = await service.subscribe(customer_id, request)

        assert subscription is not None
        assert subscription.customer_id == customer_id
        assert subscription.status == SubscriptionStatus.TRIAL
        assert subscription.trial_ends_at is not None

    async def test_subscribe_without_trial(
        self, service: SubscriptionService, db_session: AsyncSession
    ):
        """Test subscribing to a plan without trial."""
        venue_id = uuid4()
        plan = SubscriptionPlan(
            venue_id=venue_id,
            name="No Trial Plan",
            billing_interval=BillingInterval.MONTHLY,
            price=Decimal("29.99"),
            currency="USD",
            trial_days=0,
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)

        customer_id = uuid4()
        request = SubscribeRequest(plan_id=plan.id)

        subscription = await service.subscribe(customer_id, request)

        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.trial_ends_at is None

    async def test_pause_subscription(
        self, service: SubscriptionService, subscription_plan: SubscriptionPlan
    ):
        """Test pausing a subscription."""
        customer_id = uuid4()
        sub_request = SubscribeRequest(plan_id=subscription_plan.id)
        subscription = await service.subscribe(customer_id, sub_request)

        # Make it active first (skip trial)
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.trial_ends_at = None

        resume_date = datetime.utcnow() + timedelta(days=14)
        pause_request = PauseSubscriptionRequest(
            resume_date=resume_date,
            reason="Going on vacation",
        )

        pause = await service.pause_subscription(subscription.id, pause_request)

        assert pause is not None
        assert pause.scheduled_resume.date() == resume_date.date()

        # Verify subscription status
        updated = await service.get_subscription(subscription.id)
        assert updated.status == SubscriptionStatus.PAUSED

    async def test_cancel_subscription(
        self, service: SubscriptionService, subscription_plan: SubscriptionPlan
    ):
        """Test cancelling a subscription."""
        customer_id = uuid4()
        sub_request = SubscribeRequest(plan_id=subscription_plan.id)
        subscription = await service.subscribe(customer_id, sub_request)

        cancel_request = CancelSubscriptionRequest(
            reason="No longer needed",
            immediate=False,
        )

        cancelled = await service.cancel_subscription(subscription.id, cancel_request)

        assert cancelled.status == SubscriptionStatus.PENDING_CANCELLATION
        assert cancelled.auto_renew is False

    async def test_cancel_subscription_immediate(
        self, service: SubscriptionService, subscription_plan: SubscriptionPlan
    ):
        """Test immediately cancelling a subscription."""
        customer_id = uuid4()
        sub_request = SubscribeRequest(plan_id=subscription_plan.id)
        subscription = await service.subscribe(customer_id, sub_request)

        cancel_request = CancelSubscriptionRequest(
            reason="Immediate cancellation",
            immediate=True,
        )

        cancelled = await service.cancel_subscription(subscription.id, cancel_request)

        assert cancelled.status == SubscriptionStatus.CANCELLED
        assert cancelled.ended_at is not None


class TestUsageTracking:
    """Tests for subscription usage tracking."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> SubscriptionService:
        return SubscriptionService(db_session)

    @pytest_asyncio.fixture
    async def active_subscription(
        self, db_session: AsyncSession
    ) -> CustomerSubscription:
        """Create an active subscription for testing."""
        venue_id = uuid4()
        plan = SubscriptionPlan(
            venue_id=venue_id,
            name="Usage Plan",
            billing_interval=BillingInterval.MONTHLY,
            price=Decimal("99.99"),
            currency="USD",
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

        subscription = CustomerSubscription(
            customer_id=uuid4(),
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
            next_billing_date=datetime.utcnow() + timedelta(days=30),
            metadata={},
        )
        db_session.add(subscription)
        await db_session.commit()
        await db_session.refresh(subscription)
        return subscription

    async def test_track_usage(
        self, service: SubscriptionService, active_subscription: CustomerSubscription
    ):
        """Test tracking usage for a subscription."""
        result = await service.track_usage(
            subscription_id=active_subscription.id,
            usage_type="api_calls",
            quantity=10,
        )

        assert result["usage_type"] == "api_calls"
        assert result["current_usage"] == 10

        # Track more usage
        result2 = await service.track_usage(
            subscription_id=active_subscription.id,
            usage_type="api_calls",
            quantity=5,
        )

        assert result2["current_usage"] == 15
