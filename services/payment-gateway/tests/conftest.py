"""
Test configuration and fixtures for Payment Gateway Service.
"""

import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app
from app.models.base import Base
from app.core.dependencies import get_db


# Test database URL
TEST_DATABASE_URL = settings.database_url.replace(
    "/payment_gateway", "/payment_gateway_test"
)

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API tests."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Create sync HTTP client for simple tests."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_venue_id() -> str:
    """Sample venue UUID."""
    return str(uuid4())


@pytest.fixture
def sample_customer_id() -> str:
    """Sample customer UUID."""
    return str(uuid4())


@pytest.fixture
def sample_user_id() -> str:
    """Sample user UUID."""
    return str(uuid4())


@pytest.fixture
def sample_charge_request(sample_venue_id, sample_customer_id) -> dict:
    """Sample charge request data."""
    return {
        "venue_id": sample_venue_id,
        "customer_id": sample_customer_id,
        "amount": "99.99",
        "currency": "USD",
        "token": "pm_test_token_123",
        "description": "Test payment",
    }


@pytest.fixture
def sample_subscription_request(
    sample_venue_id, sample_customer_id
) -> dict:
    """Sample subscription request data."""
    return {
        "customer_id": sample_customer_id,
        "venue_id": sample_venue_id,
        "payment_method_id": str(uuid4()),
        "plan_name": "Monthly Membership",
        "billing_interval": "monthly",
        "amount": "29.99",
        "currency": "USD",
    }


@pytest.fixture
def mock_jwt_token() -> str:
    """Mock JWT token for authentication."""
    from jose import jwt
    from datetime import datetime, timedelta

    payload = {
        "sub": str(uuid4()),
        "email": "test@example.com",
        "role": "admin",
        "venue_ids": [],
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_headers(mock_jwt_token) -> dict:
    """Authentication headers for API requests."""
    return {"Authorization": f"Bearer {mock_jwt_token}"}


# =============================================================================
# MOCK PROCESSOR FIXTURES
# =============================================================================

@pytest.fixture
def mock_stripe_processor():
    """Mock Stripe processor for tests."""
    from unittest.mock import AsyncMock, MagicMock
    from app.services.processors import ProcessorResult, TokenizeResult, RefundResult

    processor = MagicMock()
    processor.charge = AsyncMock(return_value=ProcessorResult(
        success=True,
        transaction_id="pi_test_123",
        raw_response={"status": "succeeded"},
    ))
    processor.authorize = AsyncMock(return_value=ProcessorResult(
        success=True,
        transaction_id="pi_test_auth_123",
        raw_response={"status": "requires_capture"},
    ))
    processor.capture = AsyncMock(return_value=ProcessorResult(
        success=True,
        transaction_id="pi_test_123",
        raw_response={"status": "succeeded"},
    ))
    processor.void = AsyncMock(return_value=ProcessorResult(
        success=True,
        transaction_id="pi_test_123",
        raw_response={"status": "canceled"},
    ))
    processor.refund = AsyncMock(return_value=RefundResult(
        success=True,
        refund_id="re_test_123",
        raw_response={"status": "succeeded"},
    ))
    processor.tokenize_card = AsyncMock(return_value=TokenizeResult(
        success=True,
        token="pm_test_tokenized",
        card_brand="visa",
        card_last_four="4242",
        card_exp_month=12,
        card_exp_year=2025,
    ))
    processor.create_customer = AsyncMock(return_value={
        "id": "cus_test_123",
        "email": "test@example.com",
    })

    return processor


@pytest.fixture
def mock_square_processor():
    """Mock Square processor for tests."""
    from unittest.mock import AsyncMock, MagicMock
    from app.services.processors import ProcessorResult

    processor = MagicMock()
    processor.charge = AsyncMock(return_value=ProcessorResult(
        success=True,
        transaction_id="sq_payment_123",
        raw_response={"payment": {"status": "COMPLETED"}},
    ))

    return processor
