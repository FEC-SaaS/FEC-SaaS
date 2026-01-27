# Payment Gateway Service - Testing Guide

This guide covers testing strategies, running tests, and best practices for the Payment Gateway Service.

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and configuration
├── unit/                 # Unit tests
│   ├── test_payment_service.py
│   ├── test_fraud_service.py
│   ├── test_refund_service.py
│   └── test_subscription_service.py
└── integration/          # Integration tests
    ├── test_payment_api.py
    ├── test_subscription_api.py
    └── test_webhook_handlers.py
```

## Running Tests

### Quick Start

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/unit/test_payment_service.py

# Run specific test
poetry run pytest tests/unit/test_payment_service.py::TestPaymentService::test_charge_success
```

### Test Coverage

```bash
# Run with coverage report
poetry run pytest --cov=app --cov-report=term-missing

# Generate HTML coverage report
poetry run pytest --cov=app --cov-report=html
open htmlcov/index.html

# Fail if coverage is below threshold
poetry run pytest --cov=app --cov-fail-under=80
```

### Test Markers

```bash
# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests
poetry run pytest tests/integration/

# Run async tests
poetry run pytest -m asyncio

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
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
```

### Environment for Tests

Create a `.env.test` file:

```env
ENVIRONMENT=test
DEBUG=true
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/payment_gateway_test
JWT_SECRET_KEY=test-secret-key
ENCRYPTION_KEY=test-encryption-key-32chars
STRIPE_API_KEY=sk_test_xxx
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

## Writing Tests

### Unit Test Example

```python
"""Test payment service."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.payment_service import PaymentService
from app.schemas.payment import ChargeRequest


class TestPaymentService:
    """Unit tests for PaymentService."""

    @pytest.mark.asyncio
    async def test_charge_success(self, db_session, mock_stripe_processor):
        """Test successful payment charge."""
        service = PaymentService(db_session)

        # Setup mocks
        with patch.object(service, 'get_processor', new_callable=AsyncMock) as mock_proc:
            mock_config = MagicMock(id=uuid4())
            mock_proc.return_value = (mock_stripe_processor, mock_config)

            # Setup fraud check to pass
            with patch.object(service.fraud_service, 'check_transaction', new_callable=AsyncMock) as mock_fraud:
                mock_fraud.return_value = MagicMock(
                    passed=True,
                    fraud_score=Decimal("10"),
                    risk_level="low",
                    triggered_rules=[],
                    recommended_action="allow",
                )

                with patch.object(service, '_get_payment_token', new_callable=AsyncMock) as mock_token:
                    mock_token.return_value = "pm_test_123"

                    request = ChargeRequest(
                        venue_id=uuid4(),
                        amount=Decimal("99.99"),
                        currency="USD",
                        token="pm_test_123",
                    )

                    result = await service.charge(request)

                    assert result.status.value == "completed"
                    assert result.amount == Decimal("99.99")
```

### Integration Test Example

```python
"""Test payment API endpoints."""
import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestPaymentEndpoints:
    """Integration tests for payment API."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health endpoint returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_charge_requires_auth(self, client: AsyncClient):
        """Test that charge endpoint requires authentication."""
        response = await client.post(
            "/api/v1/payments/charge",
            json={
                "venue_id": str(uuid4()),
                "amount": "99.99",
                "currency": "USD",
                "token": "pm_test",
            },
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_charge_with_auth(self, client: AsyncClient, auth_headers):
        """Test charge endpoint with authentication."""
        response = await client.post(
            "/api/v1/payments/charge",
            headers=auth_headers,
            json={
                "venue_id": str(uuid4()),
                "amount": "99.99",
                "currency": "USD",
                "token": "pm_test_123",
            },
        )
        # Will fail without proper processor config, but auth should pass
        assert response.status_code != 403
```

## Testing Fixtures

### Database Session Fixture

```python
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

### Mock Processor Fixture

```python
@pytest.fixture
def mock_stripe_processor():
    """Mock Stripe processor for unit tests."""
    processor = MagicMock()
    processor.charge = AsyncMock(return_value=ProcessorResult(
        success=True,
        transaction_id="pi_test_123",
    ))
    processor.refund = AsyncMock(return_value=RefundResult(
        success=True,
        refund_id="re_test_123",
    ))
    return processor
```

### Auth Headers Fixture

```python
@pytest.fixture
def auth_headers(mock_jwt_token) -> dict:
    """Provide authentication headers."""
    return {"Authorization": f"Bearer {mock_jwt_token}"}
```

## Testing Scenarios

### Payment Processing Tests

| Scenario | Test Type | Expected Result |
|----------|-----------|-----------------|
| Successful charge | Unit | Transaction created with COMPLETED status |
| Card declined | Unit | Transaction created with DECLINED status |
| Fraud blocked | Unit | Transaction blocked, alert created |
| Network error | Unit | Transaction fails gracefully |
| Authorization | Unit | Transaction in AUTHORIZED status |
| Capture | Unit | Authorized transaction captured |
| Void | Unit | Transaction voided |

### Fraud Detection Tests

| Scenario | Test Type | Expected Result |
|----------|-----------|-----------------|
| Low risk transaction | Unit | Passes with low score |
| High velocity | Unit | Blocked, alert created |
| Amount threshold exceeded | Unit | Flagged for review |
| Blocked country | Unit | Transaction blocked |
| Known fraud IP | Unit | Transaction blocked |

### Subscription Tests

| Scenario | Test Type | Expected Result |
|----------|-----------|-----------------|
| Create subscription | Integration | Subscription created in ACTIVE status |
| Cancel subscription | Integration | Status changes to CANCELLED |
| Pause/Resume | Integration | Status changes appropriately |
| Payment failure | Unit | Retry logic triggered |
| Expiration | Unit | Status changes to EXPIRED |

## Mocking External Services

### Stripe API Mocking

```python
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_stripe():
    """Mock Stripe SDK."""
    with patch("stripe.PaymentIntent") as mock_pi:
        mock_pi.create.return_value = MagicMock(
            id="pi_test_123",
            status="succeeded",
        )
        yield mock_pi
```

### RabbitMQ Mocking

```python
@pytest.fixture
def mock_event_publisher():
    """Mock event publisher."""
    with patch("app.services.event_publisher.EventPublisher") as mock:
        mock.publish = AsyncMock()
        yield mock
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Payment Gateway Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
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

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test
        run: |
          poetry run pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Performance Testing

### Load Testing with Locust

```python
# locustfile.py
from locust import HttpUser, task, between

class PaymentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Get auth token
        self.token = self.get_token()

    @task(3)
    def charge_payment(self):
        self.client.post(
            "/api/v1/payments/charge",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "venue_id": "test-venue-id",
                "amount": "99.99",
                "currency": "USD",
                "token": "pm_test",
            },
        )

    @task(1)
    def list_payments(self):
        self.client.get(
            "/api/v1/payments/?venue_id=test-venue-id",
            headers={"Authorization": f"Bearer {self.token}"},
        )
```

Run load tests:

```bash
locust -f locustfile.py --host=http://localhost:8004
```

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures to set up and tear down data
- Don't rely on test execution order

### 2. Mock External Services
- Always mock payment processors in unit tests
- Mock RabbitMQ for event publishing tests
- Use test/sandbox modes for integration tests

### 3. Test Data Management
- Use factories for creating test data
- Clean up data after tests
- Use realistic but anonymized data

### 4. Assertion Best Practices
- Test one thing per test
- Use descriptive assertion messages
- Verify side effects (events, database changes)

### 5. Code Coverage Goals
- Aim for 80%+ coverage on business logic
- 100% coverage on critical payment paths
- Focus on meaningful tests, not just coverage numbers

## Debugging Tests

### Running with Debug Output

```bash
# Show print statements
poetry run pytest -s

# Stop on first failure
poetry run pytest -x

# Show local variables on failure
poetry run pytest -l

# Enter debugger on failure
poetry run pytest --pdb
```

### Common Issues

**Async Test Failures**
```python
# Make sure pytest-asyncio is installed
# Use @pytest.mark.asyncio decorator
# Set asyncio_mode = auto in pytest.ini
```

**Database State Issues**
```python
# Ensure tests use transaction rollback
# Check fixture scope (function vs session)
# Verify cleanup in teardown
```

**Mock Not Applied**
```python
# Check patch target path
# Ensure mock is applied before import
# Use patch.object for instance methods
```
