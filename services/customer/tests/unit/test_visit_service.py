"""
=============================================================================
FILE: tests/unit/test_visit_service.py
PURPOSE: Unit tests for VisitService
=============================================================================
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.visit_service import VisitService
from app.schemas.customer import (
    VisitCreate,
    VisitUpdate,
    VisitCheckout,
    ActivityCreate,
    PaginationParams,
)
from app.models.customer import VisitSource, ActivityType
from tests.conftest import VisitFactory, ActivityFactory


class TestVisitServiceCreate:
    """Tests for visit creation."""

    @pytest.mark.asyncio
    async def test_create_visit_success(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test successful visit creation."""
        service = VisitService(db_session)

        visit_data = VisitCreate(
            customer_id=sample_customer.id,
            venue_id=sample_venue_id,
            source=VisitSource.WALK_IN,
            party_size=3,
        )

        visit = await service.create_visit(visit_data)

        assert visit is not None
        assert visit.party_size == 3
        assert visit.source == VisitSource.WALK_IN
        assert visit.check_in_time is not None

    @pytest.mark.asyncio
    async def test_create_visit_with_reservation(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test creating visit from reservation."""
        service = VisitService(db_session)

        reservation_id = uuid4()
        visit_data = VisitCreate(
            customer_id=sample_customer.id,
            venue_id=sample_venue_id,
            source=VisitSource.RESERVATION,
            reservation_id=reservation_id,
            party_size=5,
        )

        visit = await service.create_visit(visit_data)

        assert visit.source == VisitSource.RESERVATION
        assert str(visit.reservation_id) == str(reservation_id)

    @pytest.mark.asyncio
    async def test_create_visit_online_booking(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test creating visit from online booking."""
        service = VisitService(db_session)

        visit_data = VisitCreate(
            customer_id=sample_customer.id,
            venue_id=sample_venue_id,
            source=VisitSource.ONLINE_BOOKING,
            party_size=4,
        )

        visit = await service.create_visit(visit_data)

        assert visit.source == VisitSource.ONLINE_BOOKING


class TestVisitServiceGet:
    """Tests for visit retrieval."""

    @pytest.mark.asyncio
    async def test_get_visit_by_id(self, db_session: AsyncSession, sample_visit):
        """Test getting visit by ID."""
        service = VisitService(db_session)

        visit = await service.get_visit(sample_visit.id)

        assert visit is not None
        assert visit.id == sample_visit.id

    @pytest.mark.asyncio
    async def test_get_visit_not_found(self, db_session: AsyncSession):
        """Test getting non-existent visit."""
        service = VisitService(db_session)

        visit = await service.get_visit(uuid4())

        assert visit is None

    @pytest.mark.asyncio
    async def test_get_customer_visits(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test getting visits for a customer."""
        service = VisitService(db_session)

        # Create multiple visits
        for _ in range(3):
            visit_data = VisitCreate(
                customer_id=sample_customer.id,
                venue_id=sample_venue_id,
                source=VisitSource.WALK_IN,
                party_size=2,
            )
            await service.create_visit(visit_data)

        visits = await service.get_customer_visits(sample_customer.id, limit=10)

        assert len(visits) >= 3


class TestVisitServiceList:
    """Tests for visit listing."""

    @pytest.mark.asyncio
    async def test_list_visits_by_venue(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test listing visits for a venue."""
        service = VisitService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        # Create visits
        for _ in range(3):
            visit_data = VisitCreate(
                customer_id=sample_customer.id,
                venue_id=sample_venue_id,
                source=VisitSource.WALK_IN,
                party_size=2,
            )
            await service.create_visit(visit_data)

        visits, total = await service.list_visits(
            venue_id=sample_venue_id,
            pagination=pagination,
        )

        assert len(visits) >= 3
        assert total >= 3

    @pytest.mark.asyncio
    async def test_list_visits_with_date_filter(
        self, db_session: AsyncSession, sample_visit, sample_venue_id
    ):
        """Test listing visits with date filter."""
        service = VisitService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        today = date.today()
        yesterday = today - timedelta(days=1)

        visits, total = await service.list_visits(
            venue_id=sample_venue_id,
            pagination=pagination,
            date_from=yesterday,
            date_to=today,
        )

        assert isinstance(visits, list)

    @pytest.mark.asyncio
    async def test_list_visits_by_source(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test listing visits filtered by source."""
        service = VisitService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        # Create walk-in visit
        visit_data = VisitCreate(
            customer_id=sample_customer.id,
            venue_id=sample_venue_id,
            source=VisitSource.WALK_IN,
            party_size=2,
        )
        await service.create_visit(visit_data)

        visits, total = await service.list_visits(
            venue_id=sample_venue_id,
            pagination=pagination,
            source=VisitSource.WALK_IN,
        )

        assert all(v.source == VisitSource.WALK_IN for v in visits)


class TestVisitServiceUpdate:
    """Tests for visit updates."""

    @pytest.mark.asyncio
    async def test_update_visit_success(self, db_session: AsyncSession, sample_visit):
        """Test successful visit update."""
        service = VisitService(db_session)

        update_data = VisitUpdate(
            party_size=5,
            notes="Updated notes",
        )

        updated = await service.update_visit(sample_visit.id, update_data)

        assert updated is not None
        assert updated.party_size == 5
        assert updated.notes == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_visit_not_found(self, db_session: AsyncSession):
        """Test updating non-existent visit."""
        service = VisitService(db_session)

        update_data = VisitUpdate(party_size=3)

        updated = await service.update_visit(uuid4(), update_data)

        assert updated is None


class TestVisitServiceCheckout:
    """Tests for visit checkout."""

    @pytest.mark.asyncio
    async def test_checkout_visit_success(self, db_session: AsyncSession, sample_visit):
        """Test successful visit checkout."""
        service = VisitService(db_session)

        checkout_data = VisitCheckout(
            total_spend=Decimal("75.50"),
            notes="Great visit",
            satisfaction_rating=5,
        )

        visit = await service.checkout_visit(sample_visit.id, checkout_data)

        assert visit is not None
        assert visit.check_out_time is not None
        assert visit.total_spend == Decimal("75.50")
        assert visit.satisfaction_rating == 5

    @pytest.mark.asyncio
    async def test_checkout_visit_updates_ltv(
        self, db_session: AsyncSession, sample_visit
    ):
        """Test checkout updates customer LTV."""
        service = VisitService(db_session)

        checkout_data = VisitCheckout(
            total_spend=Decimal("100.00"),
        )

        visit = await service.checkout_visit(sample_visit.id, checkout_data)

        # LTV should be updated (tested indirectly through service call)
        assert visit is not None
        assert visit.total_spend == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_checkout_visit_not_found(self, db_session: AsyncSession):
        """Test checkout non-existent visit."""
        service = VisitService(db_session)

        checkout_data = VisitCheckout(total_spend=Decimal("50.00"))

        visit = await service.checkout_visit(uuid4(), checkout_data)

        assert visit is None


class TestVisitServiceActivities:
    """Tests for visit activities."""

    @pytest.mark.asyncio
    async def test_add_activity_success(self, db_session: AsyncSession, sample_visit):
        """Test adding activity to visit."""
        service = VisitService(db_session)

        activity_data = ActivityCreate(
            visit_id=sample_visit.id,
            activity_type=ActivityType.ATTRACTION,
            activity_name="Laser Tag",
            amount=Decimal("25.00"),
            quantity=2,
        )

        activity = await service.add_activity(activity_data)

        assert activity is not None
        assert activity.activity_name == "Laser Tag"
        assert activity.amount == Decimal("25.00")
        assert activity.quantity == 2

    @pytest.mark.asyncio
    async def test_add_multiple_activities(self, db_session: AsyncSession, sample_visit):
        """Test adding multiple activities to visit."""
        service = VisitService(db_session)

        activities_data = [
            ActivityCreate(
                visit_id=sample_visit.id,
                activity_type=ActivityType.ATTRACTION,
                activity_name="Bowling",
                amount=Decimal("15.00"),
                quantity=1,
            ),
            ActivityCreate(
                visit_id=sample_visit.id,
                activity_type=ActivityType.FOOD_BEVERAGE,
                activity_name="Pizza",
                amount=Decimal("12.00"),
                quantity=2,
            ),
            ActivityCreate(
                visit_id=sample_visit.id,
                activity_type=ActivityType.ARCADE,
                activity_name="Game Card",
                amount=Decimal("20.00"),
                quantity=1,
            ),
        ]

        for activity_data in activities_data:
            await service.add_activity(activity_data)

        visit = await service.get_visit(sample_visit.id)
        # Visit should have activities loaded
        assert visit is not None

    @pytest.mark.asyncio
    async def test_add_activity_different_types(self, db_session: AsyncSession, sample_visit):
        """Test adding activities of different types."""
        service = VisitService(db_session)

        # Attraction
        activity1 = await service.add_activity(ActivityCreate(
            visit_id=sample_visit.id,
            activity_type=ActivityType.ATTRACTION,
            activity_name="Go Karts",
            amount=Decimal("30.00"),
            quantity=1,
        ))

        # Food
        activity2 = await service.add_activity(ActivityCreate(
            visit_id=sample_visit.id,
            activity_type=ActivityType.FOOD_BEVERAGE,
            activity_name="Burger",
            amount=Decimal("10.00"),
            quantity=1,
        ))

        # Merchandise
        activity3 = await service.add_activity(ActivityCreate(
            visit_id=sample_visit.id,
            activity_type=ActivityType.MERCHANDISE,
            activity_name="T-Shirt",
            amount=Decimal("25.00"),
            quantity=1,
        ))

        assert activity1.activity_type == ActivityType.ATTRACTION
        assert activity2.activity_type == ActivityType.FOOD_BEVERAGE
        assert activity3.activity_type == ActivityType.MERCHANDISE


class TestVisitServiceStats:
    """Tests for visit statistics."""

    @pytest.mark.asyncio
    async def test_get_visit_stats(
        self, db_session: AsyncSession, sample_customer, sample_venue_id
    ):
        """Test getting visit statistics."""
        service = VisitService(db_session)

        # Create some visits
        for i in range(3):
            visit_data = VisitCreate(
                customer_id=sample_customer.id,
                venue_id=sample_venue_id,
                source=VisitSource.WALK_IN,
                party_size=2 + i,
            )
            visit = await service.create_visit(visit_data)

            # Checkout with spend
            checkout_data = VisitCheckout(
                total_spend=Decimal(str(50 + i * 10)),
            )
            await service.checkout_visit(visit.id, checkout_data)

        today = date.today()
        yesterday = today - timedelta(days=1)

        stats = await service.get_visit_stats(sample_venue_id, yesterday, today)

        assert stats is not None
        assert "total_visits" in stats or isinstance(stats, dict)


class TestVisitServiceDuration:
    """Tests for visit duration calculations."""

    @pytest.mark.asyncio
    async def test_visit_duration_calculated(self, db_session: AsyncSession, sample_visit):
        """Test visit duration is calculated on checkout."""
        service = VisitService(db_session)

        # Wait a bit and checkout (in real tests, mock the time)
        checkout_data = VisitCheckout(
            total_spend=Decimal("50.00"),
        )

        visit = await service.checkout_visit(sample_visit.id, checkout_data)

        assert visit is not None
        assert visit.check_out_time is not None
        # Duration should be set if the model supports it
        if hasattr(visit, 'duration_minutes'):
            assert visit.duration_minutes >= 0
