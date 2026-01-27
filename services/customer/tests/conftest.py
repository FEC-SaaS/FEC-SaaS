"""
=============================================================================
FILE: tests/conftest.py
PURPOSE: Pytest fixtures for Customer Service tests
=============================================================================
"""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.models.customer import (
    Customer,
    CustomerFamily,
    CustomerFamilyMember,
    CustomerVisit,
    CustomerActivity,
    CustomerSegment,
    CustomerLTV,
    CustomerChurnRisk,
    CustomerPreference,
    CustomerType,
    SegmentType,
    RiskLevel,
    VisitSource,
    ActivityType,
    RelationshipType,
)
from app.core.dependencies import get_db, get_current_user


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with dependency overrides."""

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return {
            "user_id": str(uuid4()),
            "email": "test@example.com",
            "role": "admin",
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# FACTORY CLASSES
# =============================================================================

class CustomerFactory:
    """Factory for creating test Customer objects."""

    @staticmethod
    def create(
        venue_id: str = None,
        customer_type: CustomerType = CustomerType.B2C,
        first_name: str = "John",
        last_name: str = "Doe",
        email: str = None,
        phone: str = None,
        **kwargs
    ) -> Customer:
        venue_id = venue_id or str(uuid4())
        return Customer(
            id=uuid4(),
            venue_id=venue_id,
            customer_type=customer_type,
            first_name=first_name,
            last_name=last_name,
            email=email or f"test_{uuid4().hex[:8]}@example.com",
            phone=phone or f"+1555{uuid4().hex[:7]}",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **kwargs
        )

    @staticmethod
    def create_dict(
        venue_id: str = None,
        customer_type: str = "individual",
        first_name: str = "John",
        last_name: str = "Doe",
        **kwargs
    ) -> dict:
        venue_id = venue_id or str(uuid4())
        return {
            "venue_id": venue_id,
            "customer_type": customer_type,
            "first_name": first_name,
            "last_name": last_name,
            "email": kwargs.get("email", f"test_{uuid4().hex[:8]}@example.com"),
            "phone": kwargs.get("phone", f"+1555{uuid4().hex[:7]}"),
            **kwargs
        }


class FamilyFactory:
    """Factory for creating test CustomerFamily objects."""

    @staticmethod
    def create(
        venue_id: str = None,
        family_name: str = "Smith Family",
        primary_customer_id: str = None,
        **kwargs
    ) -> CustomerFamily:
        venue_id = venue_id or str(uuid4())
        return CustomerFamily(
            id=uuid4(),
            venue_id=venue_id,
            family_name=family_name,
            primary_customer_id=primary_customer_id or uuid4(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **kwargs
        )

    @staticmethod
    def create_dict(
        venue_id: str = None,
        family_name: str = "Smith Family",
        primary_customer_id: str = None,
        **kwargs
    ) -> dict:
        venue_id = venue_id or str(uuid4())
        return {
            "venue_id": venue_id,
            "family_name": family_name,
            "primary_customer_id": primary_customer_id or str(uuid4()),
            **kwargs
        }


class FamilyMemberFactory:
    """Factory for creating test CustomerFamilyMember objects."""

    @staticmethod
    def create(
        family_id: str = None,
        customer_id: str = None,
        relation_type: RelationshipType = RelationshipType.OTHER,
        **kwargs
    ) -> CustomerFamilyMember:
        return CustomerFamilyMember(
            id=uuid4(),
            family_id=family_id or str(uuid4()),
            customer_id=customer_id or str(uuid4()),
            relation_type=relation_type,
            created_at=datetime.utcnow(),
            **kwargs
        )


class VisitFactory:
    """Factory for creating test CustomerVisit objects."""

    @staticmethod
    def create(
        customer_id: str = None,
        venue_id: str = None,
        source: VisitSource = VisitSource.WALK_IN,
        check_in_time: datetime = None,
        **kwargs
    ) -> CustomerVisit:
        return CustomerVisit(
            id=uuid4(),
            customer_id=customer_id or str(uuid4()),
            venue_id=venue_id or str(uuid4()),
            source=source,
            check_in_time=check_in_time or datetime.utcnow(),
            guest_count=kwargs.get("guest_count", 2),
            adult_count=kwargs.get("adult_count", 2),
            child_count=kwargs.get("child_count", 0),
            total_spend=kwargs.get("total_spend", Decimal("50.00")),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **kwargs
        )

    @staticmethod
    def create_dict(
        customer_id: str = None,
        venue_id: str = None,
        source: str = "walk_in",
        **kwargs
    ) -> dict:
        return {
            "customer_id": customer_id or str(uuid4()),
            "venue_id": venue_id or str(uuid4()),
            "source": source,
            "guest_count": kwargs.get("guest_count", 2),
            **kwargs
        }


class ActivityFactory:
    """Factory for creating test CustomerActivity objects."""

    @staticmethod
    def create(
        visit_id: str = None,
        activity_type: ActivityType = ActivityType.BOWLING,
        **kwargs
    ) -> CustomerActivity:
        return CustomerActivity(
            id=uuid4(),
            visit_id=visit_id or str(uuid4()),
            activity_type=activity_type,
            activity_name=kwargs.get("activity_name", "Laser Tag"),
            amount_spent=kwargs.get("amount_spent", Decimal("25.00")),
            start_time=kwargs.get("start_time", datetime.utcnow()),
            created_at=datetime.utcnow(),
            **kwargs
        )


class SegmentFactory:
    """Factory for creating test CustomerSegment objects."""

    @staticmethod
    def create(
        customer_id: str = None,
        segment_type: SegmentType = SegmentType.STANDARD,
        score: int = 50,
        **kwargs
    ) -> CustomerSegment:
        return CustomerSegment(
            id=uuid4(),
            customer_id=customer_id or str(uuid4()),
            segment_type=segment_type,
            score=score,
            assigned_at=datetime.utcnow(),
            **kwargs
        )


class LTVFactory:
    """Factory for creating test CustomerLTV objects."""

    @staticmethod
    def create(
        customer_id: str = None,
        total_revenue: Decimal = Decimal("500.00"),
        **kwargs
    ) -> CustomerLTV:
        return CustomerLTV(
            id=uuid4(),
            customer_id=customer_id or str(uuid4()),
            total_revenue=total_revenue,
            total_visits=kwargs.get("total_visits", 10),
            calculated_ltv=kwargs.get("calculated_ltv", Decimal("1000.00")),
            visit_frequency=kwargs.get("visit_frequency", Decimal("2.00")),
            avg_spend=kwargs.get("avg_spend", Decimal("50.00")),
            expected_lifespan_months=kwargs.get("expected_lifespan_months", 12),
            first_visit_date=kwargs.get("first_visit_date", date.today() - timedelta(days=365)),
            last_visit_date=kwargs.get("last_visit_date", date.today() - timedelta(days=7)),
            **kwargs
        )


class ChurnRiskFactory:
    """Factory for creating test CustomerChurnRisk objects."""

    @staticmethod
    def create(
        customer_id: str = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        risk_score: Decimal = Decimal("25.00"),
        **kwargs
    ) -> CustomerChurnRisk:
        return CustomerChurnRisk(
            id=uuid4(),
            customer_id=customer_id or str(uuid4()),
            risk_level=risk_level,
            risk_score=risk_score,
            days_since_last_visit=kwargs.get("days_since_last_visit", 14),
            visit_frequency_trend=kwargs.get("visit_frequency_trend", "stable"),
            spend_trend=kwargs.get("spend_trend", "stable"),
            confidence=kwargs.get("confidence", Decimal("75.00")),
            **kwargs
        )


class PreferenceFactory:
    """Factory for creating test CustomerPreference objects."""

    @staticmethod
    def create(
        customer_id: str = None,
        preference_type: str = "favorite_activity",
        preference_value: str = "Laser Tag",
        **kwargs
    ) -> CustomerPreference:
        return CustomerPreference(
            id=uuid4(),
            customer_id=customer_id or str(uuid4()),
            preference_type=preference_type,
            preference_value=preference_value,
            is_stated=kwargs.get("is_stated", False),
            confidence_score=kwargs.get("confidence_score", Decimal("85.00")),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **kwargs
        )


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_venue_id() -> str:
    """Sample venue ID for tests."""
    return str(uuid4())


@pytest.fixture
def sample_customer_data(sample_venue_id) -> dict:
    """Sample customer creation data."""
    return CustomerFactory.create_dict(venue_id=sample_venue_id)


@pytest.fixture
def sample_family_data(sample_venue_id) -> dict:
    """Sample family creation data."""
    return FamilyFactory.create_dict(venue_id=sample_venue_id)


@pytest_asyncio.fixture
async def sample_customer(db_session: AsyncSession, sample_venue_id) -> Customer:
    """Create and persist a sample customer."""
    customer = CustomerFactory.create(venue_id=sample_venue_id)
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@pytest_asyncio.fixture
async def sample_customers(db_session: AsyncSession, sample_venue_id) -> list[Customer]:
    """Create and persist multiple sample customers."""
    customers = [
        CustomerFactory.create(
            venue_id=sample_venue_id,
            first_name=f"Customer{i}",
            last_name="Test"
        )
        for i in range(5)
    ]
    for customer in customers:
        db_session.add(customer)
    await db_session.commit()
    for customer in customers:
        await db_session.refresh(customer)
    return customers


@pytest_asyncio.fixture
async def sample_family(db_session: AsyncSession, sample_venue_id, sample_customer) -> CustomerFamily:
    """Create and persist a sample family."""
    family = FamilyFactory.create(
        venue_id=sample_venue_id,
        primary_customer_id=sample_customer.id
    )
    db_session.add(family)
    await db_session.commit()
    await db_session.refresh(family)
    return family


@pytest_asyncio.fixture
async def sample_visit(
    db_session: AsyncSession,
    sample_customer: Customer,
    sample_venue_id
) -> CustomerVisit:
    """Create and persist a sample visit."""
    visit = VisitFactory.create(
        customer_id=str(sample_customer.id),
        venue_id=sample_venue_id
    )
    db_session.add(visit)
    await db_session.commit()
    await db_session.refresh(visit)
    return visit


@pytest_asyncio.fixture
async def sample_segment(
    db_session: AsyncSession,
    sample_customer: Customer
) -> CustomerSegment:
    """Create and persist a sample segment."""
    segment = SegmentFactory.create(customer_id=str(sample_customer.id))
    db_session.add(segment)
    await db_session.commit()
    await db_session.refresh(segment)
    return segment


@pytest_asyncio.fixture
async def sample_ltv(
    db_session: AsyncSession,
    sample_customer: Customer
) -> CustomerLTV:
    """Create and persist a sample LTV record."""
    ltv = LTVFactory.create(customer_id=str(sample_customer.id))
    db_session.add(ltv)
    await db_session.commit()
    await db_session.refresh(ltv)
    return ltv


@pytest_asyncio.fixture
async def sample_churn_risk(
    db_session: AsyncSession,
    sample_customer: Customer
) -> CustomerChurnRisk:
    """Create and persist a sample churn risk record."""
    churn_risk = ChurnRiskFactory.create(customer_id=str(sample_customer.id))
    db_session.add(churn_risk)
    await db_session.commit()
    await db_session.refresh(churn_risk)
    return churn_risk


# =============================================================================
# MOCK SERVICES
# =============================================================================

class MockRedisClient:
    """Mock Redis client for testing."""

    def __init__(self):
        self._data = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._data[key] = value

    async def delete(self, key: str):
        self._data.pop(key, None)

    async def keys(self, pattern: str):
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]


@pytest.fixture
def mock_redis():
    """Mock Redis client fixture."""
    return MockRedisClient()


class MockNotificationClient:
    """Mock notification service client."""

    def __init__(self):
        self.sent_notifications = []

    async def send_email(self, to: str, subject: str, body: str):
        self.sent_notifications.append({
            "type": "email",
            "to": to,
            "subject": subject,
            "body": body
        })
        return {"status": "sent"}

    async def send_sms(self, to: str, message: str):
        self.sent_notifications.append({
            "type": "sms",
            "to": to,
            "message": message
        })
        return {"status": "sent"}


@pytest.fixture
def mock_notification_client():
    """Mock notification client fixture."""
    return MockNotificationClient()


# =============================================================================
# AUTH FIXTURES
# =============================================================================

@pytest.fixture
def auth_headers() -> dict:
    """Authorization headers for API tests."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def admin_user() -> dict:
    """Admin user context."""
    return {
        "user_id": str(uuid4()),
        "email": "admin@example.com",
        "role": "admin",
    }


@pytest.fixture
def staff_user() -> dict:
    """Staff user context."""
    return {
        "user_id": str(uuid4()),
        "email": "staff@example.com",
        "role": "staff",
    }
