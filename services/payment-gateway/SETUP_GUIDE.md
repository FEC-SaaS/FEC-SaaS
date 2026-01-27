# Payment Gateway Service - Setup Guide

This guide will walk you through setting up the Payment Gateway Service for development and production environments.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- RabbitMQ 3.11+
- Poetry (Python package manager)
- Stripe account (for Stripe integration)
- Square account (for Square integration)

## Development Setup

### 1. Clone the Repository

```bash
cd services/payment-gateway
```

### 2. Install Dependencies

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install
```

### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Service Configuration
SERVICE_NAME=payment-gateway
ENVIRONMENT=development
DEBUG=true
PORT=8004

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/payment_gateway

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
ENCRYPTION_KEY=your-32-character-encryption-key

# Stripe Configuration
STRIPE_API_KEY=sk_test_your_stripe_test_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Square Configuration
SQUARE_ACCESS_TOKEN=your_square_sandbox_token
SQUARE_ENVIRONMENT=sandbox
SQUARE_LOCATION_ID=your_location_id

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Fraud Detection Thresholds
FRAUD_SCORE_MEDIUM_THRESHOLD=30
FRAUD_SCORE_HIGH_THRESHOLD=60
FRAUD_SCORE_CRITICAL_THRESHOLD=80
```

### 4. Set Up Database

```bash
# Create the database
createdb payment_gateway

# Run migrations
poetry run alembic upgrade head
```

### 5. Start the Service

```bash
# Development mode with auto-reload
poetry run uvicorn app.main:app --reload --port 8004

# Or using the main module directly
poetry run python -m app.main
```

### 6. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8004/health

# Check API docs (development only)
open http://localhost:8004/docs
```

## Payment Processor Setup

### Stripe Setup

1. **Create a Stripe Account**
   - Go to [stripe.com](https://stripe.com) and create an account
   - Navigate to Developers > API Keys

2. **Get API Keys**
   - Copy your test secret key (starts with `sk_test_`)
   - Set it as `STRIPE_API_KEY` in your `.env`

3. **Configure Webhooks**
   - Go to Developers > Webhooks
   - Add endpoint: `https://your-domain/api/v1/webhooks/stripe/{venue_id}`
   - Select events:
     - `payment_intent.succeeded`
     - `payment_intent.payment_failed`
     - `charge.dispute.created`
     - `charge.dispute.updated`
     - `charge.dispute.closed`
     - `invoice.payment_failed`
     - `customer.subscription.*`
   - Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET`

4. **For Local Development**
   ```bash
   # Use Stripe CLI to forward webhooks
   stripe listen --forward-to localhost:8004/api/v1/webhooks/stripe/{venue_id}
   ```

### Square Setup

1. **Create a Square Developer Account**
   - Go to [developer.squareup.com](https://developer.squareup.com)
   - Create an application

2. **Get Credentials**
   - Copy Sandbox Access Token
   - Note your Location ID
   - Set in `.env`:
     ```env
     SQUARE_ACCESS_TOKEN=your_token
     SQUARE_ENVIRONMENT=sandbox
     SQUARE_LOCATION_ID=your_location
     ```

3. **Configure Webhooks**
   - Go to Webhooks in your Square Dashboard
   - Add endpoint: `https://your-domain/api/v1/webhooks/square/{venue_id}`
   - Subscribe to:
     - `payment.completed`
     - `payment.failed`
     - `dispute.created`

## Database Configuration

### Create Venue Payment Config

After setting up processors, create venue configurations:

```python
# Example: Create venue payment config via API or database
from uuid import uuid4
from app.models.payment import PaymentProcessor, VenuePaymentConfig, ProcessorType

# First, ensure processors exist
stripe_processor = PaymentProcessor(
    id=uuid4(),
    processor_name="Stripe",
    processor_type=ProcessorType.STRIPE,
    supported_methods=["card"],
    supported_currencies=["USD", "EUR", "GBP"],
)

# Then create venue config
venue_config = VenuePaymentConfig(
    id=uuid4(),
    venue_id=your_venue_id,
    processor_id=stripe_processor.id,
    merchant_id="your_stripe_account_id",
    api_credentials={
        "api_key": encrypt_sensitive_data("sk_test_xxx"),
        "webhook_secret": "whsec_xxx",
    },
    is_primary=True,
    is_active=True,
)
```

## Docker Setup

### Build and Run with Docker

```dockerfile
# Dockerfile is provided in the repository
docker build -t payment-gateway .

# Run with environment variables
docker run -d \
  --name payment-gateway \
  -p 8004:8004 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e JWT_SECRET_KEY=... \
  -e STRIPE_API_KEY=... \
  payment-gateway
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  payment-gateway:
    build: ./services/payment-gateway
    ports:
      - "8004:8004"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/payment_gateway
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
    depends_on:
      - db
      - rabbitmq

  db:
    image: postgres:14
    environment:
      POSTGRES_DB: payment_gateway
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "15672:15672"

volumes:
  pgdata:
```

## Production Deployment

### Security Checklist

- [ ] Use strong, unique values for `JWT_SECRET_KEY` and `ENCRYPTION_KEY`
- [ ] Use production API keys from Stripe/Square
- [ ] Enable HTTPS for all endpoints
- [ ] Configure proper CORS origins
- [ ] Set `DEBUG=false`
- [ ] Use managed PostgreSQL with encryption at rest
- [ ] Enable database connection pooling
- [ ] Set up log aggregation
- [ ] Configure rate limiting

### Environment Variables for Production

```env
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=["https://your-admin-portal.com"]

# Use production keys
STRIPE_API_KEY=sk_live_xxx
SQUARE_ENVIRONMENT=production
```

### Health Checks

Configure your orchestrator to check:
- `/health` - Basic health check
- `/health/ready` - Readiness check including database

### Scaling Considerations

- The service is stateless and can be horizontally scaled
- Use a load balancer for multiple instances
- Configure database connection pool size based on instance count
- RabbitMQ should be clustered for high availability

## Troubleshooting

### Common Issues

**Database Connection Failed**
```
Check DATABASE_URL format and credentials
Ensure PostgreSQL is running and accessible
Verify database exists: createdb payment_gateway
```

**Migration Errors**
```bash
# Check current migration state
poetry run alembic current

# Reset migrations (development only!)
poetry run alembic downgrade base
poetry run alembic upgrade head
```

**Stripe Webhook Failures**
```
Verify webhook secret is correct
Check webhook endpoint URL
Use Stripe CLI for local testing
Review Stripe Dashboard for failed deliveries
```

**RabbitMQ Connection Issues**
```
Verify RabbitMQ is running
Check connection URL format
Ensure virtual host exists
```

## Support

For issues or questions:
1. Check the [README.md](./README.md)
2. Review the [TESTING_GUIDE.md](./TESTING_GUIDE.md)
3. Open an issue in the repository
