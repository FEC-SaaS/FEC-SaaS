# Membership Service Testing Guide

This guide covers testing strategies and execution for the Membership Service.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_subscriptions.py # Subscription tests
├── test_loyalty.py      # Loyalty program tests
└── test_api.py          # API integration tests
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
poetry install --with dev

# Or install specific test packages
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite
```

### Run All Tests

```bash
# Run all tests
poetry run pytest

# With verbose output
poetry run pytest -v

# With coverage report
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/test_subscriptions.py

# Run specific test class
poetry run pytest tests/test_subscriptions.py::TestSubscriptionPlanCRUD

# Run specific test
poetry run pytest tests/test_subscriptions.py::TestSubscriptionPlanCRUD::test_create_subscription_plan
```

### Test Configuration

Tests use an in-memory SQLite database by default for speed and isolation. Configure in `conftest.py`:

```python
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
```

For testing against PostgreSQL:

```python
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/membership_test"
```

## Test Categories

### Unit Tests

Test individual service methods in isolation.

```python
# tests/test_subscriptions.py

class TestSubscriptionPlanCRUD:
    """Unit tests for subscription plan operations."""

    async def test_create_subscription_plan(self, service, venue_id, sample_subscription_plan_data):
        plan_data = SubscriptionPlanCreate(**sample_subscription_plan_data)
        plan = await service.create_plan(venue_id, plan_data)

        assert plan is not None
        assert plan.name == sample_subscription_plan_data["name"]
        assert plan.is_active is True
```

### Integration Tests

Test API endpoints with the full request/response cycle.

```python
# tests/test_api.py

class TestSubscriptionEndpoints:
    @pytest.mark.asyncio
    async def test_create_plan_with_auth(self, client, admin_jwt_token, admin_user):
        response = await client.post(
            f"/api/v1/subscriptions/plans?venue_id={admin_user['venue_id']}",
            json={"name": "Test Plan", "billing_interval": "monthly", "price": "29.99"},
            headers={"Authorization": f"Bearer {admin_jwt_token}"},
        )
        assert response.status_code == 201
```

### Service Tests

Test business logic and service interactions.

```python
# tests/test_loyalty.py

class TestPointsTransactions:
    async def test_earn_points(self, service, loyalty_account):
        request = EarnPointsRequest(points=100, reference_type="purchase")
        transaction = await service.earn_points(loyalty_account.id, request)

        assert transaction.points == 100
        account = await service.get_account(loyalty_account.id)
        assert account.points_balance == 100
```

## Test Fixtures

### Common Fixtures

```python
# conftest.py

@pytest_asyncio.fixture
async def db_session(test_engine):
    """Create a test database session."""
    async with async_session_maker() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def client(db_session):
    """Create a test HTTP client."""
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_jwt_token(test_user):
    """Generate mock JWT for testing."""
    return jwt.encode({
        "sub": str(test_user["user_id"]),
        "customer_id": str(test_user["customer_id"]),
        "exp": datetime.utcnow() + timedelta(hours=1),
    }, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

### Domain-Specific Fixtures

```python
@pytest_asyncio.fixture
async def subscription_plan(db_session) -> SubscriptionPlan:
    """Create a test subscription plan."""
    plan = SubscriptionPlan(
        venue_id=uuid4(),
        name="Test Plan",
        billing_interval=BillingInterval.MONTHLY,
        price=Decimal("49.99"),
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    return plan

@pytest_asyncio.fixture
async def loyalty_account(db_session) -> CustomerLoyaltyAccount:
    """Create a test loyalty account."""
    # Create program and account
    ...
```

## Testing Patterns

### Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_operation(service):
    result = await service.async_method()
    assert result is not None
```

### Testing Error Cases

```python
async def test_redeem_insufficient_points(service, loyalty_account):
    request = RedeemPointsRequest(points=10000)  # More than balance

    with pytest.raises(ValueError, match="Insufficient points"):
        await service.redeem_points(loyalty_account.id, request)
```

### Testing Authentication

```python
async def test_endpoint_requires_auth(client):
    response = await client.post("/api/v1/protected-endpoint")
    assert response.status_code == 403

async def test_endpoint_with_auth(client, jwt_token):
    response = await client.post(
        "/api/v1/protected-endpoint",
        headers={"Authorization": f"Bearer {jwt_token}"}
    )
    assert response.status_code == 200
```

### Testing Events

```python
@pytest.fixture
def mock_event_publisher(mocker):
    return mocker.patch("app.services.event_publisher.event_publisher.publish")

async def test_subscription_publishes_event(service, subscription_plan, mock_event_publisher):
    customer_id = uuid4()
    await service.subscribe(customer_id, SubscribeRequest(plan_id=subscription_plan.id))

    mock_event_publisher.assert_called_once()
```

## Coverage Requirements

Aim for high coverage on critical paths:

| Module | Target Coverage |
|--------|----------------|
| Services | 90%+ |
| API Routes | 85%+ |
| Models | 80%+ |
| Utils | 75%+ |

Generate coverage report:

```bash
poetry run pytest --cov=app --cov-report=html --cov-report=term-missing
```

View HTML report at `htmlcov/index.html`.

## Writing New Tests

### Test File Template

```python
"""
Tests for [feature name] functionality.
"""

import pytest
import pytest_asyncio
from uuid import uuid4

from app.services import YourService
from app.schemas.membership import YourSchema


class TestYourFeature:
    """Tests for [description]."""

    @pytest_asyncio.fixture
    async def service(self, db_session):
        return YourService(db_session)

    async def test_happy_path(self, service):
        """Test successful [operation]."""
        result = await service.your_method()
        assert result is not None

    async def test_error_case(self, service):
        """Test [error condition]."""
        with pytest.raises(ValueError):
            await service.your_method(invalid_input)
```

### Test Naming Conventions

- `test_<feature>_<scenario>` - e.g., `test_subscribe_with_trial`
- `test_<feature>_<error_type>` - e.g., `test_redeem_insufficient_points`
- `test_<endpoint>_<http_method>` - e.g., `test_plans_endpoint_get`

## Mocking External Services

### Mock Payment Gateway

```python
@pytest.fixture
def mock_payment_service(mocker):
    mock = mocker.patch("app.services.payment_client.PaymentClient")
    mock.return_value.charge.return_value = {"success": True, "payment_id": "pay_123"}
    return mock
```

### Mock RabbitMQ

```python
@pytest.fixture
def mock_rabbitmq(mocker):
    return mocker.patch("aio_pika.connect_robust")
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

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

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Run tests
        run: poetry run pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Performance Testing

For load testing subscription endpoints:

```python
# tests/performance/test_load.py
import asyncio
from httpx import AsyncClient

async def test_concurrent_subscriptions():
    """Test handling many concurrent subscription requests."""
    async with AsyncClient(base_url="http://localhost:8005") as client:
        tasks = [
            client.post("/api/v1/subscriptions", json={...})
            for _ in range(100)
        ]
        responses = await asyncio.gather(*tasks)
        success_count = sum(1 for r in responses if r.status_code == 201)
        assert success_count >= 95  # 95% success rate
```

## Troubleshooting Tests

### Common Issues

1. **"Event loop is closed"**
   ```python
   # Use session-scoped event loop
   @pytest.fixture(scope="session")
   def event_loop():
       loop = asyncio.new_event_loop()
       yield loop
       loop.close()
   ```

2. **"Database not initialized"**
   - Ensure fixtures run in correct order
   - Check that `test_engine` fixture creates tables

3. **"Token invalid"**
   - Verify JWT_SECRET_KEY in test config matches

4. **"Fixture not found"**
   - Check fixture imports in conftest.py
   - Ensure fixture scope is correct
