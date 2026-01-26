"""
=============================================================================
FILE: tests/conftest.py
PURPOSE: Pytest fixtures for Party Service tests
=============================================================================

Provides shared fixtures for both unit and integration tests including
database setup, mock services, test data factories, and API client.
"""

import asyncio
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from faker import Faker
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.models.party import (
    PartyPackage,
    PartyAddon,
    PartyPackageAddon,
    PartyBooking,
    PartyBookingAddon,
    CorporateEvent,
    PartyTimeline,
    PartyHostAssignment,
    PackageType,
    AddonType,
    BookingType,
    BookingStatus,
    CorporateEventType,
    CorporateEventStatus,
    TimelineStatus,
    HostRole,
)
from app.core.dependencies import get_db, get_current_user


fake = Faker()


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for testing with SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test."""
    async_session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================


@pytest.fixture
def mock_current_user() -> dict:
    """Mock current user data."""
    return {
        "user_id": str(uuid.uuid4()),
        "email": fake.email(),
        "role": "admin",
        "venue_id": str(uuid.uuid4()),
        "permissions": ["read", "write", "delete"],
    }


@pytest.fixture
def auth_headers(mock_current_user) -> dict:
    """Generate mock authorization headers."""
    return {
        "Authorization": "Bearer mock_token_for_testing",
        "X-User-Id": mock_current_user["user_id"],
        "X-Venue-Id": mock_current_user["venue_id"],
    }


# =============================================================================
# TEST DATA FACTORIES
# =============================================================================


class PartyPackageFactory:
    """Factory for creating test party packages."""

    @staticmethod
    def create(
        venue_id: uuid.UUID = None,
        package_name: str = None,
        package_type: PackageType = PackageType.BIRTHDAY,
        base_price: Decimal = None,
        **kwargs
    ) -> PartyPackage:
        return PartyPackage(
            id=uuid.uuid4(),
            venue_id=venue_id or uuid.uuid4(),
            package_name=package_name or f"{fake.word().capitalize()} Party Package",
            package_type=package_type,
            description=fake.text(max_nb_chars=200),
            min_guests=kwargs.get("min_guests", 8),
            max_guests=kwargs.get("max_guests", 25),
            base_price=base_price or Decimal(str(fake.random_int(min=150, max=500))),
            price_per_additional_guest=kwargs.get("price_per_additional_guest", Decimal("15.00")),
            deposit_percentage=kwargs.get("deposit_percentage", Decimal("25.00")),
            duration_minutes=kwargs.get("duration_minutes", 120),
            includes_food=kwargs.get("includes_food", True),
            includes_drinks=kwargs.get("includes_drinks", True),
            includes_cake=kwargs.get("includes_cake", False),
            includes_decorations=kwargs.get("includes_decorations", True),
            includes_invitations=kwargs.get("includes_invitations", False),
            included_activities=kwargs.get("included_activities", {}),
            display_order=kwargs.get("display_order", 0),
            is_featured=kwargs.get("is_featured", False),
            is_active=kwargs.get("is_active", True),
        )


class PartyAddonFactory:
    """Factory for creating test party addons."""

    @staticmethod
    def create(
        venue_id: uuid.UUID = None,
        addon_name: str = None,
        addon_type: AddonType = AddonType.CUSTOM,
        price: Decimal = None,
        **kwargs
    ) -> PartyAddon:
        return PartyAddon(
            id=uuid.uuid4(),
            venue_id=venue_id or uuid.uuid4(),
            addon_name=addon_name or f"{fake.word().capitalize()} Addon",
            addon_type=addon_type,
            description=fake.text(max_nb_chars=100),
            price=price or Decimal(str(fake.random_int(min=10, max=100))),
            price_type=kwargs.get("price_type", "fixed"),
            min_quantity=kwargs.get("min_quantity", 1),
            max_quantity=kwargs.get("max_quantity", None),
            requires_advance_notice_hours=kwargs.get("requires_advance_notice_hours", 0),
            display_order=kwargs.get("display_order", 0),
            is_active=kwargs.get("is_active", True),
            upsell_priority=kwargs.get("upsell_priority", 0),
        )


class PartyBookingFactory:
    """Factory for creating test party bookings."""

    @staticmethod
    def create(
        venue_id: uuid.UUID = None,
        customer_id: uuid.UUID = None,
        package_id: uuid.UUID = None,
        **kwargs
    ) -> PartyBooking:
        party_date = kwargs.get("party_date", date.today() + timedelta(days=14))
        start_time = kwargs.get("start_time", time(14, 0))
        end_time = kwargs.get("end_time", time(16, 0))
        base_price = kwargs.get("base_price", Decimal("299.99"))

        return PartyBooking(
            id=uuid.uuid4(),
            venue_id=venue_id or uuid.uuid4(),
            customer_id=customer_id or uuid.uuid4(),
            package_id=package_id or uuid.uuid4(),
            booking_type=kwargs.get("booking_type", BookingType.BIRTHDAY),
            booking_reference=kwargs.get("booking_reference", f"PB-{fake.bothify('????????').upper()}"),
            party_date=party_date,
            start_time=start_time,
            end_time=end_time,
            guest_count=kwargs.get("guest_count", 15),
            child_count=kwargs.get("child_count", 12),
            adult_count=kwargs.get("adult_count", 3),
            guest_of_honor_name=kwargs.get("guest_of_honor_name", fake.first_name()),
            guest_of_honor_age=kwargs.get("guest_of_honor_age", fake.random_int(min=4, max=12)),
            contact_name=kwargs.get("contact_name", fake.name()),
            contact_email=kwargs.get("contact_email", fake.email()),
            contact_phone=kwargs.get("contact_phone", fake.phone_number()[:20]),
            base_price=base_price,
            addons_total=kwargs.get("addons_total", Decimal("0.00")),
            tax_amount=kwargs.get("tax_amount", Decimal("0.00")),
            discount_amount=kwargs.get("discount_amount", Decimal("0.00")),
            total_price=kwargs.get("total_price", base_price),
            deposit_amount=kwargs.get("deposit_amount", base_price * Decimal("0.25")),
            deposit_paid=kwargs.get("deposit_paid", False),
            amount_paid=kwargs.get("amount_paid", Decimal("0.00")),
            balance_due=kwargs.get("balance_due", base_price),
            status=kwargs.get("status", BookingStatus.PENDING),
            special_requests=kwargs.get("special_requests", None),
            dietary_restrictions=kwargs.get("dietary_restrictions", None),
            booking_source=kwargs.get("booking_source", "web"),
            is_deleted=kwargs.get("is_deleted", False),
        )


class CorporateEventFactory:
    """Factory for creating test corporate events."""

    @staticmethod
    def create(
        venue_id: uuid.UUID = None,
        **kwargs
    ) -> CorporateEvent:
        event_date = kwargs.get("event_date", date.today() + timedelta(days=30))

        return CorporateEvent(
            id=uuid.uuid4(),
            venue_id=venue_id or uuid.uuid4(),
            company_name=kwargs.get("company_name", fake.company()),
            company_industry=kwargs.get("company_industry", fake.job()),
            company_size=kwargs.get("company_size", "SMB"),
            contact_name=kwargs.get("contact_name", fake.name()),
            contact_email=kwargs.get("contact_email", fake.company_email()),
            contact_phone=kwargs.get("contact_phone", fake.phone_number()[:20]),
            contact_title=kwargs.get("contact_title", fake.job()),
            event_type=kwargs.get("event_type", CorporateEventType.TEAM_BUILDING),
            event_name=kwargs.get("event_name", f"{fake.company()} Team Event"),
            event_date=event_date,
            start_time=kwargs.get("start_time", time(10, 0)),
            end_time=kwargs.get("end_time", time(16, 0)),
            attendee_count=kwargs.get("attendee_count", 50),
            estimated_budget=kwargs.get("estimated_budget", Decimal("5000.00")),
            status=kwargs.get("status", CorporateEventStatus.INQUIRY),
            is_deleted=kwargs.get("is_deleted", False),
        )


class PartyTimelineFactory:
    """Factory for creating test timeline items."""

    @staticmethod
    def create(
        booking_id: uuid.UUID = None,
        **kwargs
    ) -> PartyTimeline:
        return PartyTimeline(
            id=uuid.uuid4(),
            booking_id=booking_id or uuid.uuid4(),
            item_name=kwargs.get("item_name", fake.sentence(nb_words=3)),
            item_description=kwargs.get("item_description", fake.text(max_nb_chars=100)),
            item_category=kwargs.get("item_category", "activity"),
            scheduled_time=kwargs.get("scheduled_time", time(14, 0)),
            duration_minutes=kwargs.get("duration_minutes", 15),
            status=kwargs.get("status", TimelineStatus.PENDING),
            sequence_order=kwargs.get("sequence_order", 0),
        )


@pytest.fixture
def package_factory() -> PartyPackageFactory:
    """Return package factory."""
    return PartyPackageFactory()


@pytest.fixture
def addon_factory() -> PartyAddonFactory:
    """Return addon factory."""
    return PartyAddonFactory()


@pytest.fixture
def booking_factory() -> PartyBookingFactory:
    """Return booking factory."""
    return PartyBookingFactory()


@pytest.fixture
def corporate_event_factory() -> CorporateEventFactory:
    """Return corporate event factory."""
    return CorporateEventFactory()


@pytest.fixture
def timeline_factory() -> PartyTimelineFactory:
    """Return timeline factory."""
    return PartyTimelineFactory()


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_venue_id() -> uuid.UUID:
    """Return a consistent venue ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def sample_customer_id() -> uuid.UUID:
    """Return a consistent customer ID for testing."""
    return uuid.uuid4()


@pytest_asyncio.fixture
async def sample_package(db_session: AsyncSession, sample_venue_id: uuid.UUID) -> PartyPackage:
    """Create and return a sample package in the database."""
    package = PartyPackageFactory.create(
        venue_id=sample_venue_id,
        package_name="Birthday Bash Package",
        package_type=PackageType.BIRTHDAY,
        base_price=Decimal("299.99"),
    )
    db_session.add(package)
    await db_session.flush()
    await db_session.refresh(package)
    return package


@pytest_asyncio.fixture
async def sample_addon(db_session: AsyncSession, sample_venue_id: uuid.UUID) -> PartyAddon:
    """Create and return a sample addon in the database."""
    addon = PartyAddonFactory.create(
        venue_id=sample_venue_id,
        addon_name="Extra Pizza",
        addon_type=AddonType.PREMIUM_FOOD,
        price=Decimal("25.00"),
    )
    db_session.add(addon)
    await db_session.flush()
    await db_session.refresh(addon)
    return addon


@pytest_asyncio.fixture
async def sample_booking(
    db_session: AsyncSession,
    sample_venue_id: uuid.UUID,
    sample_customer_id: uuid.UUID,
    sample_package: PartyPackage,
) -> PartyBooking:
    """Create and return a sample booking in the database."""
    booking = PartyBookingFactory.create(
        venue_id=sample_venue_id,
        customer_id=sample_customer_id,
        package_id=sample_package.id,
    )
    db_session.add(booking)
    await db_session.flush()
    await db_session.refresh(booking)
    return booking


@pytest_asyncio.fixture
async def sample_corporate_event(
    db_session: AsyncSession,
    sample_venue_id: uuid.UUID,
) -> CorporateEvent:
    """Create and return a sample corporate event in the database."""
    event = CorporateEventFactory.create(venue_id=sample_venue_id)
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)
    return event


# =============================================================================
# API CLIENT FIXTURES
# =============================================================================


@pytest.fixture
def client(db_session: AsyncSession, mock_current_user: dict) -> TestClient:
    """Create a test client with overridden dependencies."""

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return mock_current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession,
    mock_current_user: dict,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with overridden dependencies."""

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return mock_current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# MOCK SERVICE FIXTURES
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.exists.return_value = False
    return redis_mock


@pytest.fixture
def mock_notification_service():
    """Mock notification service client."""
    service_mock = AsyncMock()
    service_mock.send_booking_confirmation.return_value = True
    service_mock.send_booking_reminder.return_value = True
    service_mock.send_booking_cancellation.return_value = True
    return service_mock


@pytest.fixture
def mock_venue_service():
    """Mock venue service client."""
    service_mock = AsyncMock()
    service_mock.get_venue.return_value = {
        "id": str(uuid.uuid4()),
        "name": "Test Venue",
        "address": "123 Test St",
        "is_active": True,
    }
    service_mock.check_room_availability.return_value = True
    return service_mock


@pytest.fixture
def mock_customer_service():
    """Mock customer service client."""
    service_mock = AsyncMock()
    service_mock.get_customer.return_value = {
        "id": str(uuid.uuid4()),
        "first_name": "Test",
        "last_name": "Customer",
        "email": "test@example.com",
        "phone": "555-1234",
    }
    return service_mock


# =============================================================================
# UTILITY FIXTURES
# =============================================================================


@pytest.fixture
def valid_package_data(sample_venue_id: uuid.UUID) -> dict:
    """Return valid package creation data."""
    return {
        "venue_id": str(sample_venue_id),
        "package_name": "Test Birthday Package",
        "package_type": "birthday",
        "description": "A fun birthday party package",
        "min_guests": 8,
        "max_guests": 25,
        "base_price": "299.99",
        "price_per_additional_guest": "15.00",
        "deposit_percentage": "25.00",
        "duration_minutes": 120,
        "includes_food": True,
        "includes_drinks": True,
        "includes_cake": True,
        "includes_decorations": True,
        "includes_invitations": False,
        "display_order": 1,
        "is_featured": False,
    }


@pytest.fixture
def valid_addon_data(sample_venue_id: uuid.UUID) -> dict:
    """Return valid addon creation data."""
    return {
        "venue_id": str(sample_venue_id),
        "addon_name": "Extra Pepperoni Pizza",
        "addon_type": "premium_food",
        "description": "Large pepperoni pizza for the party",
        "price": "25.00",
        "price_type": "fixed",
        "min_quantity": 1,
        "max_quantity": 10,
        "requires_advance_notice_hours": 24,
        "display_order": 1,
        "upsell_priority": 5,
        "upsell_message": "Add a delicious pizza to your party!",
    }


@pytest.fixture
def valid_booking_data(
    sample_venue_id: uuid.UUID,
    sample_customer_id: uuid.UUID,
    sample_package: PartyPackage,
) -> dict:
    """Return valid booking creation data."""
    party_date = date.today() + timedelta(days=14)
    return {
        "venue_id": str(sample_venue_id),
        "customer_id": str(sample_customer_id),
        "package_id": str(sample_package.id),
        "booking_type": "birthday",
        "party_date": party_date.isoformat(),
        "start_time": "14:00:00",
        "guest_count": 15,
        "child_count": 12,
        "adult_count": 3,
        "guest_of_honor_name": "Tommy",
        "guest_of_honor_age": 8,
        "contact_name": "John Smith",
        "contact_email": "john.smith@example.com",
        "contact_phone": "555-123-4567",
        "special_requests": "Please decorate with blue balloons",
        "dietary_restrictions": "Nut allergy",
        "booking_source": "web",
    }


@pytest.fixture
def valid_corporate_event_data(sample_venue_id: uuid.UUID) -> dict:
    """Return valid corporate event creation data."""
    event_date = date.today() + timedelta(days=30)
    return {
        "venue_id": str(sample_venue_id),
        "company_name": "Acme Corporation",
        "company_industry": "Technology",
        "company_size": "Enterprise",
        "contact_name": "Jane Doe",
        "contact_email": "jane.doe@acme.com",
        "contact_phone": "555-987-6543",
        "contact_title": "HR Manager",
        "event_type": "team_building",
        "event_name": "Annual Team Building Event",
        "event_date": event_date.isoformat(),
        "start_time": "10:00:00",
        "end_time": "16:00:00",
        "attendee_count": 75,
        "estimated_budget": "10000.00",
        "special_requests": "Need AV equipment for presentation",
        "catering_requirements": "Vegetarian options required",
        "beverage_requirements": "Open bar",
        "av_requirements": "Projector and screen",
        "space_requirements": "Large conference room",
    }
