# Reservation & Capacity Service -- Testing Guide

## Test Structure

```
tests/
  __init__.py
  conftest.py            # Shared fixtures (async db session, test client, auth overrides)
  test_services.py       # Unit tests for service-layer logic
  test_api.py            # Integration tests for API endpoints
```

- **conftest.py** -- Sets up an async SQLite in-memory database, overrides FastAPI dependencies (database session, auth), and provides an `AsyncClient` fixture via httpx.
- **test_services.py** -- Tests service functions in isolation (reservation CRUD, capacity calculations, waitlist logic, no-show scoring, analytics queries).
- **test_api.py** -- Tests HTTP endpoints end-to-end through the FastAPI test client, validating request/response contracts, status codes, and error handling.

## Running Tests

### Run All Tests

```bash
poetry run pytest
```

### Verbose Output

```bash
poetry run pytest -v
```

### With Coverage

```bash
poetry run pytest --cov=app --cov-report=term-missing
```

### Run a Specific File

```bash
poetry run pytest tests/test_services.py
poetry run pytest tests/test_api.py
```

### Run a Specific Test

```bash
poetry run pytest tests/test_services.py::test_create_reservation -v
```

## Test Categories

### Unit Tests (`test_services.py`)

Test service-layer functions with a mocked or in-memory database. These tests do not start the HTTP server.

Examples:
- Create, update, and cancel reservations
- Capacity calculation and slot availability
- Waitlist ordering and conversion
- No-show recording and reliability score computation
- Overbooking rule application
- Analytics aggregation queries
- Recurring reservation series creation (weekly, biweekly, monthly) and cancellation (all or future-only)
- Group/block booking creation with multi-resource allocation and shared group_booking_id
- Deposit lifecycle state transitions (pending, collected, refunded, forfeited)
- Conflict detection: customer double-booking prevention and resource-level overlap checking
- Input validation: past date rejection, business hours enforcement, max party size, advance booking limits
- Idempotency key deduplication logic (matching key returns existing reservation)

### Integration Tests (`test_api.py`)

Test full request/response cycles through the FastAPI app using `httpx.AsyncClient`. Auth dependencies are overridden to inject a test user token.

Examples:
- `POST /api/v1/reservations` -- create reservation and verify 201 response
- `GET /api/v1/availability?venue_id=...&date=...` -- check availability payload
- `POST /api/v1/reservations/{id}/cancel` -- cancel and verify status change
- `GET /api/v1/analytics/utilization` -- verify analytics response shape
- Error cases: 404 for missing resources, 422 for invalid input, 409 for conflicts
- `POST /api/v1/reservations/recurring` -- create recurring series and verify all occurrences
- `GET /api/v1/reservations/recurring/{group_id}` -- retrieve all reservations in a series
- `DELETE /api/v1/reservations/recurring/{group_id}` -- cancel series (all or future-only)
- `POST /api/v1/reservations/group` -- create group booking and verify shared group_booking_id
- `GET /api/v1/reservations/group/{group_id}` -- retrieve group booking details
- `DELETE /api/v1/reservations/group/{group_id}` -- cancel entire group booking
- `POST /api/v1/reservations/{id}/deposit/collect` -- collect deposit and verify status
- `POST /api/v1/reservations/{id}/deposit/refund` -- refund deposit and verify status
- `POST /api/v1/reservations/{id}/deposit/forfeit` -- forfeit deposit and verify status
- Rate limiting: verify 429 response after exceeding venue or customer request limits
- Structured error responses: verify `error_code`, `message`, and `details` fields on all error responses
- Idempotency: send duplicate request with same `idempotency_key` and verify same reservation is returned
- Input validation: verify 422 for past dates, out-of-hours times, oversized parties, and excessive advance booking
- Conflict detection: verify 409 when creating overlapping reservations for same customer or resource

## Writing New Tests

1. **Add fixtures in `conftest.py`** for any new shared state (e.g., seed data factories).
2. **Use `pytest.mark.asyncio`** (or rely on `asyncio_mode = "auto"` in `pyproject.toml`) for all async tests.
3. **Follow the Arrange-Act-Assert pattern:**

```python
async def test_create_reservation(async_client, test_db_session):
    # Arrange
    payload = {
        "venue_id": "uuid-here",
        "customer_id": "uuid-here",
        "activity_type": "bowling",
        "date": "2026-02-15",
        "time_slot": "14:00",
        "party_size": 4,
    }

    # Act
    response = await async_client.post("/api/v1/reservations", json=payload)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["party_size"] == 4
```

4. **Name tests descriptively** -- use `test_<action>_<scenario>` format (e.g., `test_cancel_reservation_already_cancelled_returns_409`).
5. **Keep tests independent** -- each test should set up its own data and not depend on execution order.

## Mocking Patterns

### Database Session

The `conftest.py` overrides the database dependency with an async SQLite session so tests run without PostgreSQL:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.database import get_db

engine = create_async_engine("sqlite+aiosqlite:///:memory:")

async def override_get_db():
    async with AsyncSession(engine) as session:
        yield session

app.dependency_overrides[get_db] = override_get_db
```

### Event Publisher

Mock the RabbitMQ event publisher to prevent actual message publishing during tests:

```python
from unittest.mock import AsyncMock
from app.services.event_publisher import EventPublisher

@pytest.fixture
def mock_event_publisher(monkeypatch):
    mock = AsyncMock(spec=EventPublisher)
    monkeypatch.setattr("app.services.reservation_service.event_publisher", mock)
    return mock
```

### Auth Dependency

Override the auth dependency to bypass JWT validation and inject a test user:

```python
from app.core.auth import get_current_user

async def override_get_current_user():
    return {
        "sub": "test-user-id",
        "email": "test@example.com",
        "role": "admin",
        "venue_id": "test-venue-id",
    }

app.dependency_overrides[get_current_user] = override_get_current_user
```

### Redis (Rate Limiting and Idempotency)

Mock the Redis client to test rate limiting and idempotency key behavior without a live Redis instance:

```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_redis():
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.incr.return_value = 1
    redis_mock.expire.return_value = True
    with patch("app.middleware.rate_limiter.get_redis", return_value=redis_mock):
        yield redis_mock
```

To test the in-memory fallback behavior, configure the mock to raise a `ConnectionError`:

```python
@pytest.fixture
def mock_redis_unavailable():
    redis_mock = AsyncMock()
    redis_mock.incr.side_effect = ConnectionError("Redis unavailable")
    with patch("app.middleware.rate_limiter.get_redis", return_value=redis_mock):
        yield redis_mock
```

### Payment Service (Deposits)

Mock the payment service HTTP client to test deposit operations without a live payment service:

```python
@pytest.fixture
def mock_payment_client(monkeypatch):
    mock = AsyncMock()
    mock.collect_deposit.return_value = {"status": "collected", "transaction_id": "txn-123"}
    mock.refund_deposit.return_value = {"status": "refunded", "transaction_id": "txn-456"}
    mock.forfeit_deposit.return_value = {"status": "forfeited", "transaction_id": "txn-789"}
    monkeypatch.setattr("app.services.reservation_service.payment_client", mock)
    return mock
```

### Notification Service

Mock the notification service HTTP client to test confirmation and reminder flows:

```python
@pytest.fixture
def mock_notification_client(monkeypatch):
    mock = AsyncMock()
    mock.send_confirmation.return_value = {"status": "sent"}
    mock.send_reminder.return_value = {"status": "sent"}
    monkeypatch.setattr("app.services.reservation_service.notification_client", mock)
    return mock
```

## Production-Readiness Test Coverage

The following areas cover the 10 production-readiness features added to the service. Each area should have both unit and integration tests.

### Rate Limiting

- Requests within the venue limit (30 req/min) succeed normally
- Requests exceeding the venue limit return 429 Too Many Requests
- Requests within the customer limit (10 req/min) succeed normally
- Requests exceeding the customer limit return 429 Too Many Requests
- In-memory fallback activates when Redis is unavailable
- Rate limit counters reset after the sliding window expires

### Input Validation

- Reservations with past dates are rejected with 422
- Reservations outside business hours are rejected with 422
- Party sizes exceeding the venue maximum are rejected with 422
- Reservations too far in advance are rejected with 422
- Valid reservations within all constraints succeed with 201

### Idempotency Keys

- First request with an `idempotency_key` creates a new reservation
- Duplicate request with the same key returns the original reservation (not a new one)
- Requests with different keys create separate reservations
- Keys expire after 24 hours (a new reservation is created after expiry)

### Composite Database Indexes

- Query performance for venue+date+status filtering is efficient (integration-level)
- Conflict detection queries use indexed lookups

### Structured Error Responses

- All 4xx and 5xx responses contain `error_code`, `message`, and `details`
- Error codes match the `ErrorCode` enum values
- Validation errors include field-level detail in `details`

### Recurring Reservations

- Weekly series creates the correct number of occurrences
- Biweekly and monthly series create correctly spaced occurrences
- Maximum of 52 occurrences is enforced
- Cancel-all removes every occurrence in the series
- Cancel-future removes only occurrences after the specified date
- All occurrences share the same `recurring_group_id`

### Group/Block Bookings

- Group booking creates reservations across multiple resources
- Party sizes up to 500 are accepted
- Party sizes exceeding 500 are rejected
- All reservations share the same `group_booking_id`
- Cancelling the group cancels all associated reservations

### Deposit/Payment Integration

- Collect deposit calls the payment service and updates reservation status
- Refund deposit calls the payment service and updates reservation status
- Forfeit deposit calls the payment service and updates reservation status
- Payment service errors are handled gracefully with appropriate error responses

### Notification Integration

- Confirmation email is sent upon reservation creation
- Reminder processing triggers notification service calls
- Notification service errors do not block reservation creation

### Conflict Detection

- Creating a reservation that overlaps with the same customer's existing booking returns 409
- Creating a reservation on the same resource at the same time returns 409
- Non-overlapping reservations for the same customer succeed
- Non-overlapping reservations on the same resource succeed
