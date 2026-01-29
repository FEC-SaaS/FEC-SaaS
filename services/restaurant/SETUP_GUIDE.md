# Restaurant Service - Setup Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- RabbitMQ 3.12+
- Redis 7+
- Poetry (Python package manager)

## Local Development Setup

### 1. Install Dependencies

```bash
cd services/restaurant
poetry install
```

### 2. Configure Environment

Copy the `.env` file and update values:

```bash
cp .env .env.local
```

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://postgres:password@localhost:5432/restaurant_db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/6` |
| `RABBITMQ_URL` | RabbitMQ AMQP connection string | `amqp://guest:guest@localhost:5672/` |
| `JWT_SECRET_KEY` | JWT signing secret (must match auth service) | `your-secret-key-change-in-production` |
| `PORT` | Service port | `8009` |
| `INVENTORY_SERVICE_URL` | Inventory service base URL (for recipe costing) | `http://localhost:8011` |

### 3. Create Database

```bash
# Create the PostgreSQL database
createdb restaurant_db

# Or via psql
psql -U postgres -c "CREATE DATABASE restaurant_db;"
```

### 4. Run Migrations

```bash
cd services/restaurant
poetry run alembic upgrade head
```

To generate a new migration after model changes:

```bash
poetry run alembic revision --autogenerate -m "description of change"
```

### 5. Start the Service

```bash
poetry run uvicorn app.main:app --reload --port 8009
```

The service will be available at `http://localhost:8009`.

- Swagger UI: `http://localhost:8009/docs`
- ReDoc: `http://localhost:8009/redoc`
- Health check: `http://localhost:8009/health`

## Docker Setup

### Build

```bash
docker build -t fec-restaurant-service .
```

### Run

```bash
docker run -p 8009:8009 \
  -e DATABASE_URL=postgresql+asyncpg://postgres:password@host.docker.internal:5432/restaurant_db \
  -e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
  -e REDIS_URL=redis://host.docker.internal:6379/6 \
  -e JWT_SECRET_KEY=your-production-secret \
  fec-restaurant-service
```

## Architecture

### Service Layer

The service follows a layered architecture:

```
API Routes (app/api/v1/) → Services (app/services/) → Models (app/models/) → Database
```

### API Route Groups

| Prefix | Module | Description |
|--------|--------|-------------|
| `/sections`, `/tables` | `tables.py` | Sections & table management |
| `/reservations` | `reservations.py` | Reservation CRUD & lifecycle |
| `/menu/*` | `menu.py` | Menu categories, items, modifiers, recipes |
| `/orders` | `orders.py` | Order management |
| `/kds/*` | `kds.py` | Kitchen Display System |
| `/bar/*` | `bar.py` | Bar inventory & pour tracking |
| `/waste/*` | `waste.py` | Food waste logging & analytics |
| `/digital-menu/*` | `digital_menu.py` | Digital menu boards |
| `/tax-config` | `tax_config.py` | Per-venue tax configuration |

All routes are prefixed with `/api/v1/restaurant/`.

### Event Publishing

The service publishes events to RabbitMQ for cross-service communication:

- `ORDER_CREATED`, `ORDER_STATUS_UPDATED` - Order lifecycle events
- `RESERVATION_CREATED`, `RESERVATION_SEATED`, `RESERVATION_CANCELLED` - Reservation events
- `MENU_ITEM_UPDATED` - Menu changes
- `KDS_ITEM_STARTED`, `KDS_ITEM_COMPLETED` - Kitchen display events
- `BAR_LOW_STOCK` - Bar inventory alerts
- `WASTE_LOGGED` - Waste tracking events

### Tax Configuration

Tax rates are configurable per venue via the `/tax-config` endpoint:

- Default tax rate: 8%
- Delivery and takeout can have separate tax rates
- Tax-inclusive pricing supported
- Falls back to default rate if no venue config exists

### Recipe Cost Calculation

The `/menu/recipes/{recipe_id}/cost` endpoint calculates recipe costs by:

1. Loading the recipe and its ingredients
2. Fetching ingredient prices from the Inventory Service
3. Computing per-ingredient and total costs
4. Returning cost per serving

## Dependencies

### Internal Services

| Service | URL Config | Purpose |
|---------|-----------|---------|
| Auth Service | `AUTH_SERVICE_URL` | JWT validation |
| Inventory Service | `INVENTORY_SERVICE_URL` | Recipe ingredient pricing |
| Notification Service | `NOTIFICATION_SERVICE_URL` | Alert delivery |
| Venue Service | `VENUE_SERVICE_URL` | Venue validation |

### Gateway Integration

The API Gateway (`services/gateway`) proxies requests to this service:

- Gateway route: `/api/v1/restaurant/*` → `http://localhost:8009`
- Port: `8009`
