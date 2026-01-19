"""Pytest configuration and fixtures for Auth Service tests."""
import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment before importing app
os.environ["AUTH_ENV"] = "test"
os.environ["AUTH_DEBUG"] = "true"
os.environ["AUTH_SECRET_KEY"] = "test-secret-key"
os.environ["AUTH_DATABASE_URL"] = "sqlite:///:memory:"

from app.db.session import Base, get_db
from app.main import app


# Create test database engine
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data() -> dict:
    """Sample user registration data."""
    return {
        "email": "test@example.com",
        "password": "SecurePass123",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def registered_user(client: TestClient, test_user_data: dict) -> dict:
    """Create and return a registered user with tokens."""
    response = client.post("/api/v1/auth/register", json=test_user_data)
    return response.json()


@pytest.fixture
def auth_headers(registered_user: dict) -> dict:
    """Return authorization headers with access token."""
    return {"Authorization": f"Bearer {registered_user['tokens']['access_token']}"}
