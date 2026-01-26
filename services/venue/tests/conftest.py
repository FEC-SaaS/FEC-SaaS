"""
=============================================================================
FILE: tests/conftest.py
PURPOSE: Pytest configuration and shared fixtures for venue service tests
=============================================================================

Provides fixtures for:
- Database sessions (test database)
- Test HTTP client
- Sample venue data
- Authentication mocking
"""

import asyncio
import uuid
from datetime import datetime, date, time
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.models.venue import (
    Venue,
    VenueHours,
    VenueSpecialHours,
    VenueSetting,
    VenueFeature,
    VenueAIConfig,
    VenuePerformance,
    VenueContact,
    VenueImage,
    VenueStatus,
    SubscriptionTier,
    OnboardingStatus,
    SettingType,
    ContactType,
    ImageType,
    AIStrategy,
)
from app.core.dependencies import get_db, get_current_user


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

# Use SQLite for testing (in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for testing."""
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


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database override."""

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "roles": ["admin"],
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_venue_data() -> dict:
    """Sample venue creation data."""
    return {
        "name": "Test Family Fun Center",
        "legal_name": "Test FEC LLC",
        "description": "A premier family entertainment center",
        "address_line1": "123 Main Street",
        "address_line2": "Suite 100",
        "city": "Dallas",
        "state": "Texas",
        "postal_code": "75001",
        "country": "USA",
        "latitude": 32.7767,
        "longitude": -96.7970,
        "timezone": "America/Chicago",
        "phone": "+1-214-555-0100",
        "email": "info@testfec.com",
        "website": "https://testfec.com",
        "subscription_tier": "pro",
        "total_capacity": 500,
        "square_footage": 25000,
    }


@pytest.fixture
def sample_venue_update_data() -> dict:
    """Sample venue update data."""
    return {
        "name": "Updated Family Fun Center",
        "description": "An updated premier family entertainment center",
        "total_capacity": 600,
    }


@pytest.fixture
def sample_hours_data() -> list:
    """Sample venue hours data for a week."""
    return [
        {"day_of_week": 0, "is_closed": True},  # Sunday closed
        {"day_of_week": 1, "open_time": "10:00:00", "close_time": "21:00:00"},
        {"day_of_week": 2, "open_time": "10:00:00", "close_time": "21:00:00"},
        {"day_of_week": 3, "open_time": "10:00:00", "close_time": "21:00:00"},
        {"day_of_week": 4, "open_time": "10:00:00", "close_time": "22:00:00"},
        {"day_of_week": 5, "open_time": "10:00:00", "close_time": "23:00:00"},
        {"day_of_week": 6, "open_time": "09:00:00", "close_time": "23:00:00"},
    ]


@pytest.fixture
def sample_special_hours_data() -> dict:
    """Sample special hours data."""
    return {
        "date": "2025-12-25",
        "name": "Christmas Day",
        "is_closed": True,
        "notes": "Closed for Christmas",
    }


@pytest.fixture
def sample_setting_data() -> dict:
    """Sample venue setting data."""
    return {
        "setting_key": "max_party_size",
        "setting_value": "50",
        "setting_type": "number",
        "description": "Maximum party size allowed",
        "category": "parties",
    }


@pytest.fixture
def sample_feature_toggle_data() -> dict:
    """Sample feature toggle data."""
    return {
        "enabled": True,
        "config": {"lanes": 24, "max_players_per_lane": 6},
    }


@pytest.fixture
def sample_ai_config_data() -> dict:
    """Sample AI configuration data."""
    return {
        "parameters": {
            "min_price_multiplier": 0.8,
            "max_price_multiplier": 1.5,
            "optimization_target": "revenue",
        }
    }


@pytest.fixture
def sample_performance_data() -> dict:
    """Sample performance metrics data."""
    return {
        "date": str(date.today()),
        "revenue": 15000.00,
        "revenue_per_guest": 45.00,
        "transaction_count": 333,
        "average_transaction": 45.00,
        "guest_count": 333,
        "new_customers": 50,
        "returning_customers": 283,
        "party_bookings": 5,
        "labor_hours": 120.0,
        "labor_cost": 2400.0,
        "labor_cost_percentage": 16.0,
        "nps_score": 72.0,
        "review_count": 15,
        "average_rating": 4.5,
        "peak_occupancy": 350,
        "capacity_utilization": 70.0,
    }


@pytest.fixture
def sample_contact_data() -> dict:
    """Sample venue contact data."""
    return {
        "contact_type": "manager",
        "name": "John Smith",
        "title": "General Manager",
        "email": "john.smith@testfec.com",
        "phone": "+1-214-555-0101",
        "is_primary": True,
    }


# =============================================================================
# MODEL FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def created_venue(db_session: AsyncSession, sample_venue_data: dict) -> Venue:
    """Create a venue in the test database."""
    venue = Venue(
        id=uuid.uuid4(),
        name=sample_venue_data["name"],
        legal_name=sample_venue_data["legal_name"],
        description=sample_venue_data["description"],
        slug="test-family-fun-center",
        address_line1=sample_venue_data["address_line1"],
        address_line2=sample_venue_data["address_line2"],
        city=sample_venue_data["city"],
        state=sample_venue_data["state"],
        postal_code=sample_venue_data["postal_code"],
        country=sample_venue_data["country"],
        latitude=sample_venue_data["latitude"],
        longitude=sample_venue_data["longitude"],
        timezone=sample_venue_data["timezone"],
        phone=sample_venue_data["phone"],
        email=sample_venue_data["email"],
        website=sample_venue_data["website"],
        subscription_tier=SubscriptionTier.PRO,
        status=VenueStatus.ACTIVE,
        onboarding_status=OnboardingStatus.COMPLETED,
        total_capacity=sample_venue_data["total_capacity"],
        square_footage=sample_venue_data["square_footage"],
    )

    db_session.add(venue)
    await db_session.commit()
    await db_session.refresh(venue)
    return venue


@pytest_asyncio.fixture
async def created_venue_with_hours(
    db_session: AsyncSession,
    created_venue: Venue,
    sample_hours_data: list,
) -> Venue:
    """Create a venue with operating hours."""
    for hour_data in sample_hours_data:
        hours = VenueHours(
            id=uuid.uuid4(),
            venue_id=created_venue.id,
            day_of_week=hour_data["day_of_week"],
            open_time=time.fromisoformat(hour_data["open_time"]) if "open_time" in hour_data else None,
            close_time=time.fromisoformat(hour_data["close_time"]) if "close_time" in hour_data else None,
            is_closed=hour_data.get("is_closed", False),
        )
        db_session.add(hours)

    await db_session.commit()
    await db_session.refresh(created_venue)
    return created_venue


@pytest_asyncio.fixture
async def created_venue_with_features(
    db_session: AsyncSession,
    created_venue: Venue,
) -> Venue:
    """Create a venue with enabled features."""
    features = ["bowling", "arcade", "food_beverage", "parties"]

    for feature_name in features:
        feature = VenueFeature(
            id=uuid.uuid4(),
            venue_id=created_venue.id,
            feature_name=feature_name,
            is_enabled=True,
            enabled_at=datetime.utcnow(),
        )
        db_session.add(feature)

    await db_session.commit()
    await db_session.refresh(created_venue)
    return created_venue


# =============================================================================
# MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_event_publisher():
    """Mock event publisher."""
    mock = AsyncMock()
    mock.publish.return_value = True
    return mock
