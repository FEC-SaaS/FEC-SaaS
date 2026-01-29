"""
=============================================================================
FILE: tests/conftest.py
PURPOSE: Pytest fixtures and configuration for Membership Service tests
=============================================================================
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.models import Base
from app.core.database import get_db
from app.config import settings

# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def test_user() -> dict:
    """Create a test user payload."""
    return {
        "user_id": uuid4(),
        "customer_id": uuid4(),
        "email": "test@example.com",
        "roles": ["user"],
        "venue_access": {},
    }


@pytest.fixture
def admin_user() -> dict:
    """Create a test admin user payload."""
    venue_id = uuid4()
    return {
        "user_id": uuid4(),
        "customer_id": uuid4(),
        "email": "admin@example.com",
        "roles": ["admin"],
        "venue_access": {str(venue_id): "admin"},
        "venue_id": venue_id,
    }


@pytest.fixture
def mock_jwt_token(test_user) -> str:
    """Generate a mock JWT token for testing."""
    import jwt
    from datetime import datetime, timedelta

    payload = {
        "sub": str(test_user["user_id"]),
        "customer_id": str(test_user["customer_id"]),
        "email": test_user["email"],
        "roles": test_user["roles"],
        "venue_access": test_user["venue_access"],
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture
def admin_jwt_token(admin_user) -> str:
    """Generate a mock admin JWT token for testing."""
    import jwt
    from datetime import datetime, timedelta

    payload = {
        "sub": str(admin_user["user_id"]),
        "customer_id": str(admin_user["customer_id"]),
        "email": admin_user["email"],
        "roles": admin_user["roles"],
        "venue_access": admin_user["venue_access"],
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture
def sample_venue_id() -> str:
    """Generate a sample venue ID."""
    return str(uuid4())


@pytest.fixture
def sample_subscription_plan_data(sample_venue_id) -> dict:
    """Sample subscription plan data."""
    return {
        "name": "Premium Monthly",
        "description": "Premium membership with all features",
        "billing_interval": "monthly",
        "price": "49.99",
        "currency": "USD",
        "trial_days": 14,
        "features": {
            "unlimited_visits": True,
            "guest_passes": 2,
            "priority_booking": True,
        },
        "max_pauses_per_year": 2,
        "max_pause_days": 30,
    }


@pytest.fixture
def sample_loyalty_program_data(sample_venue_id) -> dict:
    """Sample loyalty program data."""
    return {
        "name": "VIP Rewards",
        "description": "Earn points on every visit",
        "points_per_dollar": 10.0,
        "points_expiry_days": 365,
        "tier_multipliers": {},
        "bonus_rules": {
            "birthday_multiplier": 2.0,
            "first_purchase_bonus": 100,
        },
    }


@pytest.fixture
def sample_reward_data() -> dict:
    """Sample reward catalog data."""
    return {
        "name": "Free Game Token",
        "description": "Redeem for a free game token",
        "reward_type": "free_item",
        "points_required": 500,
        "monetary_value": "5.00",
        "quantity_available": 100,
        "max_redemptions_per_customer": 5,
        "terms_conditions": "Valid for one game only",
    }


@pytest.fixture
def sample_referral_data() -> dict:
    """Sample referral data."""
    return {
        "referrer_reward_points": 500,
        "referred_reward_points": 250,
        "expires_in_days": 90,
    }
