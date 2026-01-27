"""
=============================================================================
FILE: tests/conftest_postgres.py
PURPOSE: PostgreSQL-specific test fixtures for CI/CD integration testing
=============================================================================

This file contains fixtures specifically designed for testing against a real
PostgreSQL database. Use these fixtures in your CI/CD pipeline to ensure
compatibility with the production database.

Environment Variables Required:
- TEST_DATABASE_URL: PostgreSQL connection string for test database
  Example: postgresql+asyncpg://user:password@localhost:5432/customer_test

Usage:
    # Run PostgreSQL tests
    TEST_DATABASE_URL="postgresql+asyncpg://..." pytest tests/ --postgres

    # Or use the pytest marker
    pytest tests/ -m postgres
"""

import asyncio
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

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
# POSTGRESQL DATABASE FIXTURES
# =============================================================================

def get_postgres_test_url() -> str:
    """Get PostgreSQL test database URL from environment."""
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_test"
    )
    return url


@pytest.fixture(scope="session")
def postgres_event_loop() -> Generator:
    """Create event loop for PostgreSQL async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def postgres_engine():
    """Create async PostgreSQL test database engine.

    Uses NullPool to prevent connection pooling issues in tests.
    Creates all tables at the start of each test function and drops them after.
    """
    engine = create_async_engine(
        get_postgres_test_url(),
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def postgres_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async PostgreSQL database session for tests.

    Each test gets a fresh session with transaction rollback for isolation.
    """
    async_session_maker = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def postgres_client(postgres_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with PostgreSQL database session."""

    async def override_get_db():
        yield postgres_session

    async def override_get_current_user():
        return {
            "user_id": str(uuid4()),
            "email": "test@example.com",
            "role": "admin",
            "venue_ids": [str(uuid4())],
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# POSTGRESQL-SPECIFIC SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def pg_venue_id() -> str:
    """Sample venue ID for PostgreSQL tests."""
    return str(uuid4())


@pytest_asyncio.fixture
async def pg_customer(postgres_session: AsyncSession, pg_venue_id) -> Customer:
    """Create and persist a sample customer in PostgreSQL."""
    customer = Customer(
        id=uuid4(),
        venue_id=pg_venue_id,
        customer_type=CustomerType.B2C,
        first_name="PostgreSQL",
        last_name="TestUser",
        email=f"pg_test_{uuid4().hex[:8]}@example.com",
        phone=f"+1555{uuid4().hex[:7]}",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    postgres_session.add(customer)
    await postgres_session.commit()
    await postgres_session.refresh(customer)
    return customer


@pytest_asyncio.fixture
async def pg_customers(postgres_session: AsyncSession, pg_venue_id) -> list[Customer]:
    """Create multiple sample customers in PostgreSQL."""
    customers = []
    for i in range(5):
        customer = Customer(
            id=uuid4(),
            venue_id=pg_venue_id,
            customer_type=CustomerType.B2C,
            first_name=f"PGCustomer{i}",
            last_name="Test",
            email=f"pg_customer_{uuid4().hex[:8]}@example.com",
            phone=f"+1555{uuid4().hex[:7]}",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        postgres_session.add(customer)
        customers.append(customer)
    await postgres_session.commit()
    for customer in customers:
        await postgres_session.refresh(customer)
    return customers


@pytest_asyncio.fixture
async def pg_customer_with_segment(
    postgres_session: AsyncSession,
    pg_customer: Customer
) -> Customer:
    """Create customer with initial segment in PostgreSQL."""
    segment = CustomerSegment(
        id=uuid4(),
        customer_id=pg_customer.id,
        segment_type=SegmentType.NEW,
        score=Decimal("100.00"),
        assigned_at=datetime.utcnow(),
    )
    postgres_session.add(segment)

    ltv = CustomerLTV(
        id=uuid4(),
        customer_id=pg_customer.id,
        calculated_ltv=Decimal("0.00"),
        visit_frequency=Decimal("0.00"),
        avg_spend=Decimal("0.00"),
        total_visits=0,
        total_revenue=Decimal("0.00"),
    )
    postgres_session.add(ltv)

    churn_risk = CustomerChurnRisk(
        id=uuid4(),
        customer_id=pg_customer.id,
        risk_score=Decimal("0.00"),
        risk_level=RiskLevel.LOW,
        days_since_last_visit=0,
    )
    postgres_session.add(churn_risk)

    await postgres_session.commit()
    await postgres_session.refresh(pg_customer)
    return pg_customer


@pytest_asyncio.fixture
async def pg_family(
    postgres_session: AsyncSession,
    pg_venue_id: str,
    pg_customer: Customer
) -> CustomerFamily:
    """Create sample family in PostgreSQL."""
    family = CustomerFamily(
        id=uuid4(),
        venue_id=pg_venue_id,
        family_name="PostgreSQL Test Family",
        primary_customer_id=pg_customer.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    postgres_session.add(family)
    await postgres_session.commit()
    await postgres_session.refresh(family)
    return family


@pytest_asyncio.fixture
async def pg_visit(
    postgres_session: AsyncSession,
    pg_customer: Customer,
    pg_venue_id: str
) -> CustomerVisit:
    """Create sample visit in PostgreSQL."""
    visit = CustomerVisit(
        id=uuid4(),
        customer_id=pg_customer.id,
        venue_id=pg_venue_id,
        source=VisitSource.WALK_IN,
        check_in_time=datetime.utcnow(),
        guest_count=2,
        adult_count=2,
        child_count=0,
        total_spend=Decimal("75.00"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    postgres_session.add(visit)
    await postgres_session.commit()
    await postgres_session.refresh(visit)
    return visit


@pytest_asyncio.fixture
async def pg_visit_with_activities(
    postgres_session: AsyncSession,
    pg_visit: CustomerVisit
) -> CustomerVisit:
    """Create visit with activities in PostgreSQL."""
    activities = [
        CustomerActivity(
            id=uuid4(),
            visit_id=pg_visit.id,
            activity_type=ActivityType.ATTRACTION,
            activity_name="Laser Tag",
            amount_spent=Decimal("25.00"),
            start_time=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        CustomerActivity(
            id=uuid4(),
            visit_id=pg_visit.id,
            activity_type=ActivityType.FOOD_BEVERAGE,
            activity_name="Pizza",
            amount_spent=Decimal("15.00"),
            start_time=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
    ]
    for activity in activities:
        postgres_session.add(activity)
    await postgres_session.commit()
    await postgres_session.refresh(pg_visit)
    return pg_visit


# =============================================================================
# POSTGRESQL TEST MARKERS
# =============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "postgres: marks tests as PostgreSQL integration tests (deselect with '-m \"not postgres\"')"
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


# =============================================================================
# POSTGRESQL CONNECTION HEALTH CHECK
# =============================================================================

@pytest_asyncio.fixture(scope="session", autouse=False)
async def check_postgres_connection():
    """Verify PostgreSQL connection before running tests.

    This fixture can be used to skip PostgreSQL tests if the database
    is not available.
    """
    from sqlalchemy import text

    engine = create_async_engine(
        get_postgres_test_url(),
        poolclass=NullPool,
    )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        yield True
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")
        yield False
    finally:
        await engine.dispose()
