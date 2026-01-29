"""Test configuration and fixtures."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Fix settings before importing app
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app


TEST_VENUE_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
TEST_USER_ID = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")


@pytest.fixture
def venue_id():
    return TEST_VENUE_ID


@pytest.fixture
def user_id():
    return TEST_USER_ID


@pytest.fixture
def mock_current_user():
    return {
        "user_id": TEST_USER_ID,
        "email": "test@example.com",
        "role": "admin",
        "venue_ids": [str(TEST_VENUE_ID)],
    }


@pytest.fixture
def mock_db():
    """Mock async database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_event_publisher():
    """Mock event publisher."""
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
async def client(mock_current_user):
    """Async test client with auth overridden."""
    async def override_get_current_user():
        return mock_current_user

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
