# FEC Venue Service - Testing Guide

Comprehensive guide for testing the Venue Service, including unit tests, integration tests, and manual testing procedures.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests for service classes
│   ├── __init__.py
│   ├── test_venue_service.py
│   ├── test_hours_service.py
│   ├── test_feature_service.py
│   ├── test_settings_service.py
│   ├── test_ai_config_service.py
│   ├── test_performance_service.py
│   └── test_onboarding_service.py
├── integration/             # API endpoint tests
│   ├── __init__.py
│   ├── test_venues_api.py
│   ├── test_hours_api.py
│   ├── test_features_api.py
│   ├── test_settings_api.py
│   ├── test_ai_config_api.py
│   └── test_onboarding_api.py
└── fixtures/                # Reusable test data
    ├── __init__.py
    └── venue_fixtures.py
```

## Running Tests

### Prerequisites

```bash
# Navigate to venue service
cd services/venue

# Install dev dependencies
poetry install --with dev
```

### Run All Tests

```bash
# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html

# Verbose output
poetry run pytest -v
```

### Run Specific Test Categories

```bash
# Unit tests only
poetry run pytest tests/unit/

# Integration tests only
poetry run pytest tests/integration/

# Specific test file
poetry run pytest tests/unit/test_venue_service.py

# Specific test class
poetry run pytest tests/unit/test_venue_service.py::TestVenueService

# Specific test method
poetry run pytest tests/unit/test_venue_service.py::TestVenueService::test_create_venue_success
```

### Run Tests by Marker

```bash
# Run async tests
poetry run pytest -m asyncio

# Run slow tests
poetry run pytest -m slow

# Skip slow tests
poetry run pytest -m "not slow"
```

## Test Configuration

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
```

### conftest.py Fixtures

Key fixtures available in all tests:

| Fixture | Description |
|---------|-------------|
| `db_session` | Async database session |
| `client` | Test HTTP client |
| `sample_venue_data` | Sample venue creation data |
| `sample_hours_data` | Sample hours data |
| `created_venue` | Pre-created venue in DB |
| `created_venue_with_hours` | Venue with hours |
| `created_venue_with_features` | Venue with features |
| `mock_redis` | Mocked Redis client |

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.venue_service import VenueService
from app.schemas.venue import VenueCreate

class TestVenueService:

    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def venue_service(self, mock_db_session):
        return VenueService(mock_db_session)

    @pytest.mark.asyncio
    async def test_create_venue_success(self, venue_service, mock_db_session):
        venue_data = VenueCreate(
            name="Test FEC",
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

        result = await venue_service.create_venue(venue_data)

        assert result is not None
        mock_db_session.add.assert_called_once()
```

### Integration Test Example

```python
import pytest
from httpx import AsyncClient

class TestVenuesAPI:

    @pytest.mark.asyncio
    async def test_create_venue_success(self, client: AsyncClient, sample_venue_data):
        response = await client.post("/api/v1/venues", json=sample_venue_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_venue_data["name"]
        assert "id" in data
```

## Test Data Fixtures

Use the fixtures module for consistent test data:

```python
from tests.fixtures.venue_fixtures import (
    create_venue_data,
    create_hours_data,
    create_setting_data,
    create_performance_data,
)

# Create custom venue data
venue = create_venue_data(
    name="Custom FEC",
    subscription_tier="enterprise",
    total_capacity=1000,
)

# Create hours with custom closed day
hours = create_hours_data(closed_day=0)  # Closed Sundays
```

## Manual Testing

### Using the API

```bash
# Start the service
poetry add email-validator

poetry run uvicorn app.main:app --reload --port 8002

# Create a venue
curl -X POST http://localhost:8002/api/v1/venues \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Test FEC",
    "address_line1": "123 Main St",
    "city": "Dallas",
    "state": "Texas",
    "postal_code": "75001",
    "phone": "+1-214-555-0100",
    "email": "test@fec.com"
  }'

# Get venue
curl http://localhost:8002/api/v1/venues/<venue_id> \
  -H "Authorization: Bearer <token>"

# Update venue hours
curl -X PUT http://localhost:8002/api/v1/venues/<venue_id>/hours \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '[
    {"day_of_week": 0, "is_closed": true},
    {"day_of_week": 1, "open_time": "10:00:00", "close_time": "21:00:00"},
    ...
  ]'
```

### Using Swagger UI

1. Start the service with DEBUG=true
2. Navigate to http://localhost:8002/docs
3. Use the "Authorize" button to add JWT token
4. Test endpoints interactively

## Test Coverage

### Generate Coverage Report

```bash
# HTML report
poetry run pytest --cov=app --cov-report=html
open htmlcov/index.html

# Terminal report
poetry run pytest --cov=app --cov-report=term-missing

# XML report (for CI)
poetry run pytest --cov=app --cov-report=xml
```

### Coverage Targets

| Component | Target |
|-----------|--------|
| Services | 80%+ |
| API Routes | 70%+ |
| Models | 60%+ |
| Core utilities | 70%+ |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Venue Service Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Poetry
        run: pip install poetry

      - name: Install dependencies
        run: |
          cd services/venue
          poetry install

      - name: Run tests
        run: |
          cd services/venue
          poetry run pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Ensure PostgreSQL is running
   - Check DATABASE_URL environment variable

2. **Import errors**
   - Run `poetry install` to ensure dependencies
   - Check PYTHONPATH includes the app directory

3. **Async test failures**
   - Ensure `pytest-asyncio` is installed
   - Use `@pytest.mark.asyncio` decorator

4. **Fixture not found**
   - Check conftest.py is in the tests directory
   - Verify fixture scope is correct

### Debug Mode

```bash
# Run with debug output
poetry run pytest -v --tb=long

# Stop on first failure
poetry run pytest -x

# Run last failed tests
poetry run pytest --lf

# Drop into debugger on failure
poetry run pytest --pdb
```
