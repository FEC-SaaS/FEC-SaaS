"""Shared test fixtures for the reservation-capacity service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from httpx import ASGITransport


# ---------------------------------------------------------------------------
# Database session mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Async database session with all common operations mocked."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.close = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Event publisher mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_event_publisher():
    """Mock EventPublisher with async publish, connect, disconnect."""
    pub = AsyncMock()
    pub.publish = AsyncMock()
    pub.connect = AsyncMock()
    pub.disconnect = AsyncMock()
    return pub


# ---------------------------------------------------------------------------
# Current user override (JWT bypass)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_current_user():
    """Return a fake authenticated user dict that matches get_current_user output."""
    return {
        "user_id": uuid4(),
        "email": "testuser@example.com",
        "role": "admin",
        "venue_ids": [str(uuid4())],
    }


# ---------------------------------------------------------------------------
# Async HTTP test client (httpx + ASGI)
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client(mock_db, mock_current_user, mock_event_publisher):
    """
    Yield an httpx.AsyncClient wired to the FastAPI app with dependency
    overrides for the database session and the JWT auth dependency.
    """
    # Patch event_publisher.connect / disconnect so the lifespan does not
    # attempt a real RabbitMQ connection.
    with patch("app.main.event_publisher", mock_event_publisher):
        from app.main import app
        from app.core.database import get_db
        from app.core.auth import get_current_user

        async def _override_get_db():
            yield mock_db

        async def _override_get_current_user():
            return mock_current_user

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_get_current_user

        transport = ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

        yield client

        # Clean up overrides after test
        app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_test_client(mock_db, mock_event_publisher):
    """
    Yield an httpx.AsyncClient *without* the auth override so that
    endpoints requiring authentication return 401/403.
    """
    with patch("app.main.event_publisher", mock_event_publisher):
        from app.main import app
        from app.core.database import get_db

        async def _override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_get_db
        # Intentionally do NOT override get_current_user

        transport = ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

        yield client

        app.dependency_overrides.clear()
