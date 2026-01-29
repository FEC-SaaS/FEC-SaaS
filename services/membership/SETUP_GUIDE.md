# Membership Service Setup Guide

This guide walks you through setting up the Membership Service for development and production environments.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- RabbitMQ 3.12+
- Poetry (Python package manager)

## Development Setup

### 1. Install Dependencies

```bash
cd services/membership

# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install
```

### 2. Configure Environment

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Service Configuration
SERVICE_NAME=membership-service
ENVIRONMENT=development
DEBUG=true
PORT=8005

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/membership

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT (use same secret as auth service)
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ALGORITHM=HS256

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# External Services
PAYMENT_GATEWAY_URL=http://localhost:8004
CUSTOMER_SERVICE_URL=http://localhost:8002
```

### 3. Database Setup

#### Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE membership;
\q
```

#### Run Migrations

```bash
# Run all migrations
poetry run alembic upgrade head

# Create a new migration (after model changes)
poetry run alembic revision --autogenerate -m "description of changes"
```

### 4. Start the Service

```bash
# Development mode with auto-reload
poetry run uvicorn app.main:app --reload --port 8005

# Or using the main.py directly
poetry run python -m app.main
```

The service will be available at:
- API: http://localhost:8005
- Docs: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc

## Docker Setup

### Build Image

```bash
docker build -t membership-service .
```

### Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  membership:
    build: .
    ports:
      - "8005:8005"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/membership
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
    depends_on:
      - db
      - redis
      - rabbitmq

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: membership
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "15672:15672"

volumes:
  postgres_data:
  redis_data:
```

Run with:

```bash
docker-compose up -d
```

## Production Deployment

### Environment Configuration

For production, ensure these settings:

```env
ENVIRONMENT=production
DEBUG=false

# Use strong secrets
JWT_SECRET_KEY=<generate-strong-secret>

# Use connection pooling
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/membership?pool_size=20

# Enable SSL for external connections
```

### Database Migrations

Always run migrations before deploying new code:

```bash
alembic upgrade head
```

### Health Checks

Configure your orchestrator to use these endpoints:

- **Liveness**: `GET /health/live`
- **Readiness**: `GET /health/ready`

### Scaling Considerations

1. **Horizontal Scaling**: The service is stateless and can be horizontally scaled
2. **Database Connections**: Configure pool size based on instance count
3. **Redis**: Use Redis cluster for high availability
4. **RabbitMQ**: Configure clustering for message queue reliability

## Initial Data Setup

### Create Default Tiers

```python
# Run this script or create via API
import asyncio
from app.core.database import async_session_maker
from app.models import MembershipTier
from uuid import uuid4

async def create_default_tiers(venue_id):
    async with async_session_maker() as session:
        tiers = [
            MembershipTier(
                venue_id=venue_id,
                name="Bronze",
                level=1,
                min_points=0,
                benefits={"discount": 5},
                color="#CD7F32",
                is_active=True,
            ),
            MembershipTier(
                venue_id=venue_id,
                name="Silver",
                level=2,
                min_points=1000,
                benefits={"discount": 10, "priority_booking": True},
                color="#C0C0C0",
                is_active=True,
            ),
            MembershipTier(
                venue_id=venue_id,
                name="Gold",
                level=3,
                min_points=5000,
                benefits={"discount": 15, "priority_booking": True, "guest_passes": 2},
                color="#FFD700",
                is_active=True,
            ),
            MembershipTier(
                venue_id=venue_id,
                name="Platinum",
                level=4,
                min_points=10000,
                benefits={"discount": 20, "priority_booking": True, "guest_passes": 4, "exclusive_events": True},
                color="#E5E4E2",
                is_active=True,
            ),
        ]
        session.add_all(tiers)
        await session.commit()

# Usage:
# asyncio.run(create_default_tiers(your_venue_uuid))
```

### Create Sample Subscription Plans

```python
from decimal import Decimal
from app.models import SubscriptionPlan, BillingInterval

async def create_sample_plans(venue_id, tier_ids):
    async with async_session_maker() as session:
        plans = [
            SubscriptionPlan(
                venue_id=venue_id,
                tier_id=tier_ids["silver"],
                name="Monthly Silver",
                description="Silver membership with monthly billing",
                billing_interval=BillingInterval.MONTHLY,
                price=Decimal("29.99"),
                currency="USD",
                trial_days=7,
                features={"visits_per_month": 8},
                is_active=True,
            ),
            SubscriptionPlan(
                venue_id=venue_id,
                tier_id=tier_ids["gold"],
                name="Monthly Gold",
                description="Gold membership with monthly billing",
                billing_interval=BillingInterval.MONTHLY,
                price=Decimal("49.99"),
                currency="USD",
                trial_days=14,
                features={"unlimited_visits": True},
                is_active=True,
            ),
            SubscriptionPlan(
                venue_id=venue_id,
                tier_id=tier_ids["gold"],
                name="Annual Gold",
                description="Gold membership with annual billing (2 months free)",
                billing_interval=BillingInterval.ANNUAL,
                price=Decimal("499.99"),
                currency="USD",
                trial_days=14,
                features={"unlimited_visits": True},
                is_active=True,
            ),
        ]
        session.add_all(plans)
        await session.commit()
```

## Troubleshooting

### Database Connection Issues

```bash
# Check database connectivity
psql -U postgres -h localhost -d membership -c "SELECT 1"

# Check connection pool status in logs
# Look for "pool_size" and "overflow" metrics
```

### RabbitMQ Connection Issues

```bash
# Check RabbitMQ status
rabbitmqctl status

# Check queues
rabbitmqctl list_queues

# Management UI
# http://localhost:15672 (guest/guest)
```

### Migration Issues

```bash
# Check current migration state
alembic current

# Show migration history
alembic history

# Rollback last migration
alembic downgrade -1

# Reset to clean state (DANGER: drops all data)
alembic downgrade base
```

### Common Errors

1. **"Token has expired"**: Check JWT_SECRET_KEY matches auth service
2. **"Connection refused"**: Ensure database/Redis/RabbitMQ are running
3. **"Migration failed"**: Check for pending migrations or conflicts

## Support

For issues, check:
1. Service logs: `docker logs membership-service`
2. Health endpoint: `GET /health`
3. API documentation: `/docs`
