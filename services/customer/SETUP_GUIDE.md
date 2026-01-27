# Customer Service - Setup & Testing Guide

Complete guide for setting up, running, and testing the Customer Service.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Running the Service](#running-the-service)
5. [Running Tests](#running-tests)
6. [API Testing](#api-testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.11+**
- **Poetry** (dependency management)
- **PostgreSQL 14+**
- **Redis 6+**
- **Docker** (optional, for containerized setup)

### Verify Installations

```bash
python --version    # Should be 3.11+
poetry --version    # Should be 1.5+
psql --version      # PostgreSQL client
redis-cli --version # Redis client
```

---

## Environment Setup

### Step 1: Navigate to Service Directory

```bash
cd services/customer
```

### Step 2: Install Dependencies

```bash
# Install all dependencies including dev
poetry install

# Activate virtual environment
poetry shell
```

### Step 3: Create Environment File

```bash
# Copy example environment file
cp .env.example .env
```

### Step 4: Configure Environment Variables

Edit `.env` with your settings:

```env
# Application
APP_NAME=FEC Customer Service
VERSION=0.1.0
ENV=development
DEBUG=true
PORT=8004

# Database - UPDATE THESE
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/customer_db
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis - Customer Service uses DB 4
REDIS_URL=redis://localhost:6379/4
CACHE_TTL_SECONDS=300

# JWT - Must match Auth Service
JWT_SECRET_KEY=your-super-secret-key-must-match-auth-service
JWT_ALGORITHM=HS256

# Other Services
AUTH_SERVICE_URL=http://localhost:8000
VENUE_SERVICE_URL=http://localhost:8002
NOTIFICATION_SERVICE_URL=http://localhost:8001
PARTY_SERVICE_URL=http://localhost:8003

# Segmentation Thresholds
VIP_THRESHOLD_VISITS=10
VIP_THRESHOLD_SPEND=1000.00
PREMIUM_THRESHOLD_VISITS=5
PREMIUM_THRESHOLD_SPEND=500.00

# Feature Flags
ENABLE_CACHING=true
ENABLE_AUTO_SEGMENTATION=true
ENABLE_CHURN_PREDICTION=true
```

---

## Database Setup

### Step 1: Create PostgreSQL Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE customer_db;

# Create user (optional)
CREATE USER customer_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE customer_db TO customer_user;

# Exit
\q
```

### Step 2: Run Database Migrations

```bash
# From services/customer directory
poetry run alembic upgrade head
```

### Step 3: Create Initial Migration (if needed)

```bash
# Generate migration from models
poetry run alembic revision --autogenerate -m "Initial customer tables"

# Apply migration
poetry run alembic upgrade head
```

### Step 4: Verify Database Tables

```bash
psql -U postgres -d customer_db

# List tables
\dt

# Expected tables:
# - customers
# - customer_families
# - customer_family_members
# - customer_visits
# - customer_activities
# - customer_segments
# - customer_ltv
# - customer_churn_risks
# - customer_preferences
# - customer_next_visit_predictions
```

---

## Running the Service

### Development Mode

```bash
# Method 1: Using uvicorn directly
poetry run uvicorn app.main:app --reload --port 8004

# Method 2: Using Python
poetry run python -m uvicorn app.main:app --reload --port 8004

# Method 3: With host binding (for external access)
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8004
```

### Production Mode

```bash
# Using gunicorn with uvicorn workers
poetry run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8004
```

### Docker Mode

```bash
# Build image
docker build -t fec-customer-service .

# Run container
docker run -d \
  --name customer-service \
  -p 8004:8004 \
  --env-file .env \
  --network fec-network \
  fec-customer-service

# View logs
docker logs -f customer-service
```

### Verify Service is Running

```bash
# Health check
curl http://localhost:8004/health

# Expected response:
# {"status":"healthy","service":"customer-service","version":"0.1.0"}

# API docs
# Open in browser: http://localhost:8004/docs
```

---

## Running Tests

### Test Configuration

Tests use SQLite in-memory database by default. No external database required.

### Run All Tests

```bash
# From services/customer directory
poetry run pytest
```

### Run with Verbose Output

```bash
poetry run pytest -v
```

### Run with Coverage Report

```bash
# Run with coverage
poetry run pytest --cov=app --cov-report=html --cov-report=term-missing

# View HTML report
# Open htmlcov/index.html in browser
```

### Run Specific Test Categories

```bash
# Unit tests only
poetry run pytest tests/unit/ -v

# Integration tests only
poetry run pytest tests/integration/ -v

# Specific test file
poetry run pytest tests/unit/test_customer_service.py -v

# Specific test class
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate -v

# Specific test method
poetry run pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate::test_create_customer_success -v
```

### Run Tests with Markers

```bash
# Run only async tests
poetry run pytest -m asyncio

# Skip slow tests
poetry run pytest -m "not slow"
```

### Watch Mode (Auto-rerun on changes)

```bash
# Install pytest-watch
poetry add --group dev pytest-watch

# Run in watch mode
poetry run ptw
```

### Test Output Options

```bash
# Show print statements
poetry run pytest -s

# Show local variables on failure
poetry run pytest -l

# Stop on first failure
poetry run pytest -x

# Run last failed tests first
poetry run pytest --lf

# Run only failed tests
poetry run pytest --ff
```

---

## API Testing

### Using cURL

#### Create a Customer

```bash
curl -X POST http://localhost:8004/api/v1/customers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "venue_id": "550e8400-e29b-41d4-a716-446655440000",
    "customer_type": "individual",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone": "+15551234567"
  }'
```

#### List Customers

```bash
curl "http://localhost:8004/api/v1/customers/?venue_id=550e8400-e29b-41d4-a716-446655440000&page=1&page_size=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Get Customer Details

```bash
curl http://localhost:8004/api/v1/customers/{customer_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Create a Visit

```bash
curl -X POST http://localhost:8004/api/v1/visits/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "customer_id": "CUSTOMER_UUID",
    "venue_id": "VENUE_UUID",
    "source": "walk_in",
    "party_size": 3
  }'
```

#### Checkout Visit

```bash
curl -X PATCH http://localhost:8004/api/v1/visits/{visit_id}/checkout \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "total_spend": 85.50,
    "satisfaction_rating": 5
  }'
```

#### Get Analytics Dashboard

```bash
curl "http://localhost:8004/api/v1/analytics/dashboard?venue_id=VENUE_UUID&period_days=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Using HTTPie

```bash
# Install httpie
pip install httpie

# Create customer
http POST http://localhost:8004/api/v1/customers/ \
  Authorization:"Bearer TOKEN" \
  venue_id=UUID customer_type=individual first_name=John last_name=Doe

# List customers
http http://localhost:8004/api/v1/customers/ venue_id==UUID Authorization:"Bearer TOKEN"
```

### Using Swagger UI

1. Start the service
2. Open http://localhost:8004/docs
3. Click "Authorize" and enter your JWT token
4. Test endpoints directly from the UI

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Error

```
sqlalchemy.exc.OperationalError: connection refused
```

**Solution:**
- Verify PostgreSQL is running: `pg_isready`
- Check DATABASE_URL in .env
- Ensure database exists: `psql -l`

#### 2. Redis Connection Error

```
redis.exceptions.ConnectionError: Connection refused
```

**Solution:**
- Verify Redis is running: `redis-cli ping`
- Check REDIS_URL in .env
- Ensure correct Redis DB number (4)

#### 3. Import Error: 'settings'

```
ImportError: cannot import name 'settings' from 'app.config'
```

**Solution:**
- Ensure `settings = get_settings()` exists at the bottom of config.py

#### 4. Alembic Migration Error

```
FAILED: Target database is not up to date
```

**Solution:**
```bash
# Check current revision
poetry run alembic current

# Show history
poetry run alembic history

# Upgrade to head
poetry run alembic upgrade head
```

#### 5. Test Database Isolation

Tests should use in-memory SQLite. If tests affect your dev database:

**Solution:**
- Check conftest.py uses `sqlite+aiosqlite:///:memory:`
- Ensure test fixtures don't connect to PostgreSQL

#### 6. JWT Token Invalid

```
401 Unauthorized: Token validation failed
```

**Solution:**
- Ensure JWT_SECRET_KEY matches Auth Service
- Token may be expired, get a fresh token
- Check token format: `Bearer <token>`

### Logs and Debugging

#### Enable Debug Logging

```python
# In .env
DEBUG=true
DATABASE_ECHO=true  # SQL queries
```

#### View Detailed Logs

```bash
# Run with debug output
LOG_LEVEL=DEBUG poetry run uvicorn app.main:app --reload --port 8004
```

#### Check Service Health

```bash
# Health endpoint
curl http://localhost:8004/health

# Readiness (checks DB connection)
curl http://localhost:8004/ready
```

---

## Quick Reference

### Service Details

| Property | Value |
|----------|-------|
| Port | 8004 |
| Redis DB | 4 |
| Database | customer_db |
| API Prefix | /api/v1 |
| Docs URL | /docs |
| Health URL | /health |

### Key Commands

```bash
# Start service
poetry run uvicorn app.main:app --reload --port 8004

# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run migrations
poetry run alembic upgrade head

# Create migration
poetry run alembic revision --autogenerate -m "description"
```

### Test Files

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Shared fixtures |
| `tests/unit/test_customer_service.py` | Customer CRUD tests |
| `tests/unit/test_family_service.py` | Family tests |
| `tests/unit/test_visit_service.py` | Visit tests |
| `tests/unit/test_segmentation_service.py` | Segmentation tests |
| `tests/integration/test_customers_api.py` | Customer API tests |
| `tests/integration/test_families_api.py` | Family API tests |
| `tests/integration/test_visits_api.py` | Visit API tests |
