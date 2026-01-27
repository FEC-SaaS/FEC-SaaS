# Customer Service Testing Guide

This comprehensive guide covers all testing aspects of the Customer Service microservice, including unit tests, integration tests, API testing, and CI/CD setup.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Types](#test-types)
5. [Testing Each Feature](#testing-each-feature)
6. [Database Testing](#database-testing)
7. [Mocking External Services](#mocking-external-services)
8. [CI/CD Integration](#cicd-integration)
9. [Code Coverage](#code-coverage)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```bash
# Ensure you're in the customer service directory
cd services/customer

# Install dependencies (including dev dependencies)
poetry install --with dev

# Verify installation
poetry run pytest --version
```

### Run All Tests

```bash
# Run all tests with default SQLite (fast)
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

### Run Specific Test Types

```bash
# Unit tests only
poetry run pytest tests/unit/ -v

# Integration tests only
poetry run pytest tests/integration/ -v

# PostgreSQL integration tests (requires database)
TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/customer_test" \
  poetry run pytest -m postgres
```

---

## Test Structure

```
services/customer/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Main fixtures (SQLite)
│   ├── conftest_postgres.py        # PostgreSQL fixtures
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_customers_api.py   # Customer API tests
│   │   ├── test_families_api.py    # Family API tests
│   │   └── test_visits_api.py      # Visit API tests
│   └── unit/
│       ├── __init__.py
│       ├── test_customer_service.py    # CustomerService tests
│       ├── test_family_service.py      # FamilyService tests
│       ├── test_visit_service.py       # VisitService tests
│       └── test_segmentation_service.py # SegmentationService tests
├── pytest.ini                      # Pytest configuration
└── TESTING_GUIDE.md               # This file
```

---

## Running Tests

### Basic Commands

| Command | Description |
|---------|-------------|
| `poetry run pytest` | Run all tests |
| `poetry run pytest -v` | Verbose output |
| `poetry run pytest -x` | Stop on first failure |
| `poetry run pytest --lf` | Run last failed tests |
| `poetry run pytest -k "customer"` | Run tests matching "customer" |
| `poetry run pytest tests/unit/` | Run only unit tests |
| `poetry run pytest tests/integration/` | Run only integration tests |

### Test Selection

```bash
# Run specific test file
poetry run pytest tests/unit/test_customer_service.py

# Run specific test class
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate

# Run specific test function
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate::test_create_customer_success

# Run tests by marker
poetry run pytest -m "unit"
poetry run pytest -m "integration"
poetry run pytest -m "not slow"
```

### Parallel Execution

```bash
# Install pytest-xdist
poetry add pytest-xdist --group dev

# Run tests in parallel
poetry run pytest -n auto  # Auto-detect CPU count
poetry run pytest -n 4     # Use 4 workers
```

---

## Test Types

### 1. Unit Tests

Unit tests test individual services in isolation with mocked dependencies.

**Location:** `tests/unit/`

**Characteristics:**
- Fast execution (< 1 second each)
- No external dependencies
- Mock database and external services
- Test business logic only

**Example:**

```python
# tests/unit/test_customer_service.py
class TestCustomerServiceCreate:
    @pytest.mark.asyncio
    async def test_create_customer_success(self, db_session, sample_venue_id):
        """Test successful customer creation."""
        service = CustomerService(db_session)

        customer_data = CustomerCreate(
            venue_id=sample_venue_id,
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
        )

        customer = await service.create_customer(customer_data)

        assert customer is not None
        assert customer.first_name == "Jane"
        assert customer.is_active is True
```

### 2. Integration Tests

Integration tests test API endpoints with database interactions.

**Location:** `tests/integration/`

**Characteristics:**
- Test full request/response cycle
- Use test database (SQLite by default, PostgreSQL for CI)
- Verify HTTP status codes and response bodies
- Test authentication and authorization

**Example:**

```python
# tests/integration/test_customers_api.py
class TestCustomerCreateEndpoint:
    @pytest.mark.asyncio
    async def test_create_customer_success(self, client, sample_venue_id):
        """Test creating a new customer via API."""
        customer_data = {
            "venue_id": sample_venue_id,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }

        response = await client.post("/api/v1/customers/", json=customer_data)

        assert response.status_code == 201
        assert response.json()["first_name"] == "John"
        assert "id" in response.json()
```

### 3. PostgreSQL Integration Tests

Tests specifically for PostgreSQL compatibility.

**Location:** Uses `conftest_postgres.py` fixtures

**When to use:**
- CI/CD pipeline testing
- Testing PostgreSQL-specific features
- Verifying production compatibility

**Running:**

```bash
# Set the database URL
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/customer_test"

# Run PostgreSQL tests
poetry run pytest -m postgres

# Or include the URL inline
TEST_DATABASE_URL="..." poetry run pytest tests/integration/
```

---

## Testing Each Feature

### Customer Management

#### Create Customer

```bash
# Test customer creation
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate -v
poetry run pytest tests/integration/test_customers_api.py::TestCustomerCreateEndpoint -v
```

**Test scenarios:**
- ✅ Create customer with full data
- ✅ Create customer with minimal required data
- ✅ Create corporate (B2B) customer
- ✅ Fail on duplicate email
- ✅ Fail on duplicate phone
- ✅ Validate required fields

#### Read Customer

```bash
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceGet -v
poetry run pytest tests/integration/test_customers_api.py::TestCustomerGetEndpoint -v
```

**Test scenarios:**
- ✅ Get customer by ID
- ✅ Get customer by email
- ✅ Get customer by phone
- ✅ Return 404 for non-existent customer
- ✅ Include total visits and spend

#### Update Customer

```bash
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceUpdate -v
poetry run pytest tests/integration/test_customers_api.py::TestCustomerUpdateEndpoint -v
```

**Test scenarios:**
- ✅ Full update
- ✅ Partial update (only some fields)
- ✅ Return 404 for non-existent customer

#### Delete Customer

```bash
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceDelete -v
poetry run pytest tests/integration/test_customers_api.py::TestCustomerDeleteEndpoint -v
```

**Test scenarios:**
- ✅ Soft delete (is_active = false)
- ✅ GDPR-compliant deletion (anonymize data)
- ✅ Return 404 for non-existent customer

#### Search/List Customers

```bash
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceSearch -v
poetry run pytest tests/integration/test_customers_api.py::TestCustomerSearchEndpoint -v
```

**Test scenarios:**
- ✅ List with pagination
- ✅ Filter by customer type
- ✅ Filter by segment
- ✅ Search by query string (name, email, phone)

### Family Management

```bash
# All family tests
poetry run pytest tests/integration/test_families_api.py -v
```

**Test scenarios:**
- ✅ Create family
- ✅ Get family by ID
- ✅ Update family
- ✅ Delete family
- ✅ Add family member
- ✅ Remove family member
- ✅ Different member roles (parent, child, guardian)

### Visit Tracking

```bash
# All visit tests
poetry run pytest tests/integration/test_visits_api.py -v
```

**Test scenarios:**
- ✅ Create visit (check-in)
- ✅ Get visit by ID
- ✅ List visits with filters
- ✅ Update visit
- ✅ Checkout visit
- ✅ Add activity to visit
- ✅ Get customer visits
- ✅ Get visit statistics

### Segmentation

```bash
poetry run pytest tests/unit/test_segmentation_service.py -v
```

**Test scenarios:**
- ✅ Get customers by segment
- ✅ Get customer's segment
- ✅ Assign segment manually
- ✅ Recalculate customer segment
- ✅ Get segment statistics

### Analytics

```bash
poetry run pytest -k "analytics" -v
```

**Test scenarios:**
- ✅ Get analytics dashboard
- ✅ Get customer LTV
- ✅ Get customer churn risk
- ✅ Get revenue analytics
- ✅ Get churn analytics
- ✅ Get segment analytics

---

## Database Testing

### SQLite (Default - Fast)

SQLite is used by default for fast test execution during development.

```python
# tests/conftest.py
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
```

**Advantages:**
- No setup required
- Fast execution
- Isolated per test

### PostgreSQL (CI/CD)

Use PostgreSQL for production-like testing in CI/CD.

#### Local PostgreSQL Setup

```bash
# Using Docker
docker run -d \
  --name customer-test-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=customer_test \
  -p 5432:5432 \
  postgres:16

# Wait for database to be ready
sleep 5

# Run tests
TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/customer_test" \
  poetry run pytest tests/integration/ -v
```

#### PostgreSQL Test Fixtures

Import fixtures from `conftest_postgres.py`:

```python
# Example PostgreSQL-specific test
import pytest
from tests.conftest_postgres import pg_customer, pg_venue_id, postgres_client

class TestPostgresIntegration:
    @pytest.mark.postgres
    @pytest.mark.asyncio
    async def test_customer_crud_postgres(self, postgres_client, pg_venue_id):
        """Test customer CRUD with real PostgreSQL."""
        # Create
        response = await postgres_client.post(
            "/api/v1/customers/",
            json={
                "venue_id": pg_venue_id,
                "first_name": "PostgreSQL",
                "last_name": "Test",
                "email": "pg@test.com",
            }
        )
        assert response.status_code == 201
        customer_id = response.json()["id"]

        # Read
        response = await postgres_client.get(f"/api/v1/customers/{customer_id}")
        assert response.status_code == 200
```

---

## Mocking External Services

### Mock Event Publisher

```python
# tests/conftest.py
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_event_publisher():
    """Mock the event publisher to prevent external calls."""
    with patch('app.services.event_publisher.event_publisher') as mock:
        mock.publish_customer_created = AsyncMock(return_value=True)
        mock.publish_customer_updated = AsyncMock(return_value=True)
        mock.publish_customer_deleted = AsyncMock(return_value=True)
        mock.publish_visit_checked_in = AsyncMock(return_value=True)
        mock.publish_visit_checked_out = AsyncMock(return_value=True)
        yield mock
```

### Mock Notification Service

```python
# tests/conftest.py
class MockNotificationClient:
    def __init__(self):
        self.sent_notifications = []

    async def send_email(self, to: str, subject: str, body: str):
        self.sent_notifications.append({"type": "email", "to": to})
        return {"status": "sent"}

    async def send_sms(self, to: str, message: str):
        self.sent_notifications.append({"type": "sms", "to": to})
        return {"status": "sent"}

@pytest.fixture
def mock_notification_client():
    return MockNotificationClient()
```

### Mock Redis

```python
# tests/conftest.py
class MockRedisClient:
    def __init__(self):
        self._data = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._data[key] = value

    async def delete(self, key: str):
        self._data.pop(key, None)

@pytest.fixture
def mock_redis():
    return MockRedisClient()
```

---

## CI/CD Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/customer-service-tests.yml
name: Customer Service Tests

on:
  push:
    paths:
      - 'services/customer/**'
  pull_request:
    paths:
      - 'services/customer/**'

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: customer_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: 1.7.1

      - name: Install dependencies
        working-directory: services/customer
        run: poetry install --with dev

      - name: Run unit tests
        working-directory: services/customer
        run: poetry run pytest tests/unit/ -v --tb=short

      - name: Run integration tests (PostgreSQL)
        working-directory: services/customer
        env:
          TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/customer_test
        run: poetry run pytest tests/integration/ -v --tb=short

      - name: Generate coverage report
        working-directory: services/customer
        run: |
          poetry run pytest --cov=app --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: services/customer/coverage.xml
          flags: customer-service
```

### Docker Test Environment

```dockerfile
# Dockerfile.test
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY app/ ./app/
COPY tests/ ./tests/
COPY pytest.ini ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --with dev --no-interaction --no-ansi

# Run tests
CMD ["pytest", "-v", "--tb=short"]
```

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  customer-test-db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: customer_test
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  customer-tests:
    build:
      context: .
      dockerfile: Dockerfile.test
    depends_on:
      customer-test-db:
        condition: service_healthy
    environment:
      TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@customer-test-db:5432/customer_test
    command: pytest -v --tb=short tests/
```

Run with:
```bash
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

---

## Code Coverage

### Generate Coverage Report

```bash
# Run tests with coverage
poetry run pytest --cov=app --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Configuration

```ini
# pytest.ini
[tool:pytest-cov]
source = app
branch = True
omit =
    */tests/*
    */__pycache__/*
    */migrations/*
```

### Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| Services | > 85% | - |
| API Routes | > 80% | - |
| Models | > 90% | - |
| Overall | > 80% | - |

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

```
ModuleNotFoundError: No module named 'app'
```

**Solution:**
```bash
# Ensure you're in the correct directory
cd services/customer

# Install in development mode
poetry install
```

#### 2. Async Test Failures

```
RuntimeError: Event loop is closed
```

**Solution:** Ensure `asyncio_mode = auto` in `pytest.ini` and use `@pytest.mark.asyncio` decorator.

#### 3. Database Connection Issues

```
OperationalError: could not connect to server
```

**Solution:**
```bash
# Check PostgreSQL is running
docker ps

# Verify connection string
echo $TEST_DATABASE_URL

# Test connection
psql $TEST_DATABASE_URL -c "SELECT 1"
```

#### 4. Fixture Not Found

```
fixture 'sample_customer' not found
```

**Solution:** Ensure the fixture is defined in `conftest.py` and imported correctly.

#### 5. Test Isolation Issues

Tests failing when run together but passing individually.

**Solution:**
```bash
# Run tests in isolation mode
poetry run pytest --forked

# Or ensure proper cleanup in fixtures
@pytest_asyncio.fixture
async def db_session(async_engine):
    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Ensure rollback
```

### Debug Mode

```bash
# Run with debug output
poetry run pytest -v --tb=long -s

# Drop into debugger on failure
poetry run pytest --pdb

# Run specific test with full output
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate::test_create_customer_success -v -s
```

### Performance Profiling

```bash
# Install profiling tools
poetry add pytest-profiling --group dev

# Run with profiling
poetry run pytest --profile
```

---

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on state from other tests.

2. **Descriptive Names**: Use descriptive test names that explain what is being tested.

3. **Arrange-Act-Assert**: Follow the AAA pattern for test structure.

4. **Test Edge Cases**: Include tests for error conditions and edge cases.

5. **Use Fixtures**: Leverage pytest fixtures for common setup.

6. **Mock External Services**: Always mock external services in unit tests.

7. **Maintain Coverage**: Keep coverage above 80% for critical code.

8. **Run Tests Before Commit**: Always run tests locally before pushing.

---

## Quick Reference

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_customer_service.py

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run PostgreSQL tests
TEST_DATABASE_URL="..." poetry run pytest -m postgres

# Run parallel
poetry run pytest -n auto

# Debug mode
poetry run pytest --pdb -v -s
```
