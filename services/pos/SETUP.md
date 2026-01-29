# POS Integration Service - Setup Guide

## Prerequisites

Ensure the following are installed on your system:

- **Python 3.11+** - [python.org/downloads](https://www.python.org/downloads/)
- **Poetry** - [python-poetry.org](https://python-poetry.org/docs/#installation)
- **PostgreSQL 15+** - [postgresql.org/download](https://www.postgresql.org/download/)
- **Redis 7+** - [redis.io/download](https://redis.io/download/)
- **RabbitMQ** - [rabbitmq.com/download](https://www.rabbitmq.com/download.html)

## Database Setup

Connect to PostgreSQL and create the database and user:

```sql
CREATE USER pos_user WITH PASSWORD 'pos_pass';
CREATE DATABASE pos_db OWNER pos_user;
GRANT ALL PRIVILEGES ON DATABASE pos_db TO pos_user;
```

## Environment Configuration

Copy the example environment file and update it with your local settings:

```bash
cd services/pos
cp .env.example .env
```

Edit `.env` with the following values:

```env
# Database
DATABASE_URL=postgresql+asyncpg://pos_user:pos_pass@localhost:5432/pos_db

# Redis
REDIS_URL=redis://localhost:6379/5

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Service
SERVICE_NAME=pos-service
SERVICE_PORT=8014
LOG_LEVEL=INFO

# Auth
JWT_SECRET=your-secret-key-here

# External Services
PAYMENT_GATEWAY_URL=http://localhost:8015
NOTIFICATION_SERVICE_URL=http://localhost:8003

# External POS Integrations (optional)
TOAST_API_KEY=
SQUARE_API_KEY=
CLOVER_API_KEY=

# Caching
TAX_CACHE_TTL=3600

# Receipts
RECEIPT_TEMPLATE_DIR=./templates/receipts
```

## Installation

Install all dependencies using Poetry:

```bash
cd services/pos
poetry install
```

To install with development dependencies:

```bash
poetry install --with dev
```

## Running Migrations

Apply database migrations using Alembic:

```bash
# Run all pending migrations
poetry run alembic upgrade head

# Check current migration status
poetry run alembic current

# Generate a new migration after model changes
poetry run alembic revision --autogenerate -m "description of changes"
```

## Running the Service

Start the service in development mode with auto-reload:

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8014 --reload
```

Start the service in production mode:

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8014 --workers 4
```

## Docker Setup

Build and run the service using Docker:

```bash
# Build the image
docker build -t pos-service .

# Run the container
docker run -d \
  --name pos-service \
  -p 8014:8014 \
  -e DATABASE_URL=postgresql+asyncpg://pos_user:pos_pass@host.docker.internal:5432/pos_db \
  -e REDIS_URL=redis://host.docker.internal:6379/5 \
  -e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
  -e JWT_SECRET=your-secret-key-here \
  pos-service
```

Alternatively, use Docker Compose from the project root:

```bash
docker-compose up pos-service
```

## Verify Installation

Once the service is running, verify it is healthy:

```bash
curl http://localhost:8014/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "pos-service",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected",
  "rabbitmq": "connected"
}
```

You can also access the interactive API documentation at:

- Swagger UI: `http://localhost:8014/docs`
- ReDoc: `http://localhost:8014/redoc`
