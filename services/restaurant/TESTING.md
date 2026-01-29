# Restaurant Service - Testing Guide

## Test Setup

### Install Dev Dependencies

```bash
cd services/restaurant
poetry install --with dev
```

This installs:
- `pytest` - Test runner
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `faker` - Test data generation
- `aiosqlite` - In-memory async SQLite for tests

## Running Tests

### Run All Tests

```bash
cd services/restaurant
poetry run pytest
```

### Run with Verbose Output

```bash
poetry run pytest -v
```

### Run Specific Test File

```bash
poetry run pytest tests/test_services.py
poetry run pytest tests/test_api.py
```

### Run Specific Test Class or Method

```bash
poetry run pytest tests/test_services.py::TestTableService
poetry run pytest tests/test_services.py::TestTableService::test_create_section
```

### Run with Coverage

```bash
poetry run pytest --cov=app --cov-report=term-missing
```

### Run with Coverage HTML Report

```bash
poetry run pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Structure

```
tests/
├── __init__.py          # Package marker
├── conftest.py          # Shared fixtures (mock DB, auth, client)
├── test_services.py     # Unit tests for service layer
└── test_api.py          # Integration tests for API endpoints
```

### conftest.py - Shared Fixtures

| Fixture | Type | Description |
|---------|------|-------------|
| `venue_id` | `UUID` | Fixed test venue ID |
| `user_id` | `UUID` | Fixed test user ID |
| `mock_current_user` | `dict` | Mock authenticated user (admin role) |
| `mock_db` | `AsyncMock` | Mocked SQLAlchemy async session |
| `mock_event_publisher` | `AsyncMock` | Mocked RabbitMQ event publisher |
| `client` | `AsyncClient` | httpx async client with auth/DB overridden |

### test_services.py - Unit Tests

Tests the service layer with mocked database sessions. Each service method is tested independently.

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestTableService` | 5 | Create section, create table, list with pagination, update status, not found |
| `TestReservationService` | 4 | Create, seat, cancel, cancel not found |
| `TestMenuService` | 4 | Create category, create item, toggle availability, list with pagination |
| `TestOrderService` | 1 | Create order with items and tax calculation |
| `TestBarService` | 2 | Create inventory, list with pagination |
| `TestWasteService` | 1 | Log waste entry |

**Total: 17 unit tests**

### test_api.py - Integration Tests

Tests API endpoints through FastAPI's test client with mocked dependencies.

| Test Class | Tests | Endpoints Tested |
|------------|-------|-----------------|
| `TestHealthEndpoint` | 1 | `GET /health` |
| `TestTablesAPI` | 2 | `GET /sections`, `GET /tables` |
| `TestReservationsAPI` | 1 | `GET /reservations` |
| `TestMenuAPI` | 2 | `GET /menu/categories`, `GET /menu/items` |
| `TestOrdersAPI` | 2 | `GET /orders`, `GET /orders/{id}` (404) |
| `TestBarAPI` | 1 | `GET /bar/inventory` |
| `TestWasteAPI` | 1 | `GET /waste/analytics` |
| `TestTaxConfigAPI` | 1 | `GET /tax-config` (404) |

**Total: 11 integration tests**

## Testing Patterns

### Mocking Database Queries

For list endpoints that return paginated results, two queries run in sequence:

```python
# 1. Count query
mock_count = MagicMock()
mock_count.scalar.return_value = 5

# 2. Data query
mock_data = MagicMock()
mock_scalars = MagicMock()
mock_scalars.all.return_value = [mock_item_1, mock_item_2]
mock_data.scalars.return_value = mock_scalars

db.execute = AsyncMock(side_effect=[mock_count, mock_data])
```

### Mocking Single Record Lookups

```python
mock_result = MagicMock()
mock_result.scalar_one_or_none.return_value = mock_object  # or None for not-found
db.execute = AsyncMock(return_value=mock_result)
```

### Mocking Object Creation with Refresh

```python
async def mock_refresh(obj):
    obj.id = uuid.uuid4()
    obj.created_at = datetime.now(timezone.utc)
db.refresh = mock_refresh
```

## CI Integration

The tests are configured to run in CI via the `pytest.ini_options` in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### GitHub Actions

Tests run as part of the backend CI pipeline. The workflow expects:

```bash
cd services/restaurant
poetry install --with dev
poetry run pytest --cov=app --cov-report=xml
```
