# Reservation & Capacity Service -- Setup Guide

## Prerequisites

- **Python 3.11+**
- **Poetry** (dependency management)
- **PostgreSQL 15+**
- **Redis 7+** -- Required for rate limiting (sliding window counters) and idempotency key storage. The service uses Redis DB 7 by default. If Redis is unavailable, rate limiting falls back to an in-memory counter, but idempotency key deduplication will not function.
- **RabbitMQ 3.12+**

## Installation

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd services/reservation-capacity
```

### 2. Install Dependencies

```bash
poetry install
```

This installs both production and development dependencies into a virtual environment managed by Poetry.

### 3. Configure Environment

Copy the example environment file and update values as needed:

```bash
cp .env .env.local
```

Key variables to configure:

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@localhost:5432/reservation_capacity_db` | Update credentials for your environment |
| `REDIS_URL` | `redis://localhost:6379/7` | Uses Redis DB 7; required for rate limiting and idempotency keys |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | Update credentials for production |
| `JWT_SECRET_KEY` | `your-secret-key-change-in-production` | Must match the auth service |
| `PAYMENT_SERVICE_URL` | `http://localhost:8006` | Required for deposit collect/refund/forfeit integration |
| `NOTIFICATION_SERVICE_URL` | `http://localhost:8001` | Required for confirmation emails and reminder processing |
| `DEBUG` | `true` | Set to `false` in production |
| `ENV` | `development` | Set to `production` for deployment |

### 4. Create the Database

```bash
createdb reservation_capacity_db
```

Or via psql:

```sql
CREATE DATABASE reservation_capacity_db;
```

### 5. Run Migrations

```bash
poetry run alembic upgrade head
```

### 6. Start the Service

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8012 --reload
```

The service will be available at `http://localhost:8012`. API docs are at `http://localhost:8012/docs`.

## Docker Setup

### Build the Image

```bash
docker build -t fec-reservation-capacity-service .
```

### Run the Container

```bash
docker run -d \
  --name reservation-capacity \
  -p 8012:8012 \
  -e DATABASE_URL=postgresql+asyncpg://postgres:password@host.docker.internal:5432/reservation_capacity_db \
  -e REDIS_URL=redis://host.docker.internal:6379/7 \
  -e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
  -e JWT_SECRET_KEY=your-secret-key \
  fec-reservation-capacity-service
```

### Docker Compose

If a `docker-compose.yml` is available at the project root, start all services together:

```bash
docker compose up -d reservation-capacity
```

## Redis Setup

Redis is used for two production-readiness features:

1. **Rate Limiting** -- Sliding window counters track request rates per venue (30 req/min) and per customer (10 req/min). If Redis is down, an in-memory fallback is used automatically.
2. **Idempotency Keys** -- When a client sends an `idempotency_key` with a reservation creation request, the key is stored in Redis with a 24-hour TTL to prevent duplicate reservations on retries.

Ensure Redis is running locally or update `REDIS_URL` to point to your Redis instance:

```bash
# Start Redis locally (default port 6379)
redis-server

# Verify connectivity
redis-cli -n 7 ping
```

## External Service Dependencies

The reservation-capacity service integrates with the following services at runtime:

| Service | Variable | Purpose |
|---------|----------|---------|
| **Payment Service** | `PAYMENT_SERVICE_URL` | Deposit collection, refunds, and forfeiture via HTTP |
| **Notification Service** | `NOTIFICATION_SERVICE_URL` | Confirmation emails and scheduled reminder processing via HTTP |
| **Auth Service** | `AUTH_SERVICE_URL` | JWT validation and user context |
| **Venue Service** | `VENUE_SERVICE_URL` | Venue details and business hours lookup |
| **Customer Service** | `CUSTOMER_SERVICE_URL` | Customer data retrieval |

These services do not need to be running for the reservation-capacity service to start, but relevant features will fail gracefully if the upstream service is unavailable.

## Database Migrations

This service uses Alembic for database migrations.

### Create a New Migration

```bash
poetry run alembic revision --autogenerate -m "description of change"
```

### Apply Migrations

```bash
poetry run alembic upgrade head
```

### Rollback One Migration

```bash
poetry run alembic downgrade -1
```

### View Migration History

```bash
poetry run alembic history
```

## Running the Service

### Development (with auto-reload)

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8012 --reload
```

### Production

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8012 --workers 4
```

### Verify Health

```bash
curl http://localhost:8012/health
```
