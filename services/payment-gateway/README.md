# Payment Gateway Service

A comprehensive payment processing microservice for the FEC SaaS platform that handles all payment-related operations including charges, subscriptions, fraud detection, and dispute management.

## Features

### Payment Processing
- **Charge Processing**: Process one-time payments with automatic fraud detection
- **Authorization & Capture**: Pre-authorize payments and capture later (useful for reservations)
- **Void**: Cancel pending/authorized payments before settlement
- **Refunds**: Full and partial refund support with status tracking

### Payment Methods
- **Card Storage**: Securely store customer payment methods with PCI-compliant tokenization
- **Multiple Cards**: Customers can have multiple payment methods per venue
- **Default Selection**: Automatically manage default payment methods

### Subscriptions & Recurring Billing
- **Flexible Billing Intervals**: Daily, weekly, monthly, quarterly, yearly
- **Automatic Renewals**: Process recurring payments automatically
- **Pause/Resume**: Allow customers to pause and resume subscriptions
- **Failed Payment Handling**: Automatic retry and status management

### Fraud Detection
- **Rule-Based Detection**: Configurable fraud rules per venue or globally
- **Velocity Checks**: Monitor transaction frequency and amounts
- **Geographic Restrictions**: Block transactions from specific countries
- **Device Fingerprinting**: Track and flag suspicious devices
- **IP Address Monitoring**: Block known fraudulent IP addresses
- **Real-time Scoring**: Calculate risk scores before processing

### Dispute Management
- **Chargeback Tracking**: Monitor and manage chargebacks and inquiries
- **Evidence Submission**: Submit evidence to contest disputes
- **Metrics & Analytics**: Track win rates and dispute trends

### Payment Processors
- **Stripe Integration**: Full support for Stripe payments and subscriptions
- **Square Integration**: Support for Square payment processing
- **Extensible Design**: Easy to add new payment processors

## Architecture

```
payment-gateway/
├── app/
│   ├── api/v1/           # API routes
│   │   ├── payments.py   # Payment processing endpoints
│   │   ├── payment_methods.py  # Payment method management
│   │   ├── subscriptions.py    # Subscription endpoints
│   │   ├── fraud.py      # Fraud detection endpoints
│   │   ├── disputes.py   # Dispute management
│   │   └── webhooks.py   # Processor webhook handlers
│   ├── core/             # Core utilities
│   │   ├── dependencies.py  # FastAPI dependencies
│   │   └── encryption.py    # Data encryption utilities
│   ├── models/           # SQLAlchemy models
│   │   ├── base.py       # Base model class
│   │   └── payment.py    # Payment domain models
│   ├── schemas/          # Pydantic schemas
│   │   └── payment.py    # Request/response schemas
│   ├── services/         # Business logic
│   │   ├── processors/   # Payment processor implementations
│   │   ├── payment_service.py
│   │   ├── refund_service.py
│   │   ├── subscription_service.py
│   │   ├── fraud_service.py
│   │   ├── dispute_service.py
│   │   ├── payment_method_service.py
│   │   └── event_publisher.py
│   ├── config.py         # Configuration settings
│   └── main.py           # FastAPI application
├── alembic/              # Database migrations
├── tests/                # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── pyproject.toml        # Dependencies
└── README.md             # This file
```

## Database Schema

The service uses 10 database tables:

| Table | Description |
|-------|-------------|
| `payment_processors` | Supported payment processors (Stripe, Square, etc.) |
| `venue_payment_configs` | Per-venue processor configuration and credentials |
| `customer_payment_methods` | Stored customer payment methods (tokenized) |
| `payment_transactions` | All payment transactions and their status |
| `payment_refunds` | Refund records linked to original payments |
| `subscription_payments` | Recurring subscription records |
| `fraud_detection_rules` | Configurable fraud detection rules |
| `fraud_alerts` | Triggered fraud alerts requiring review |
| `payment_disputes` | Chargebacks and dispute records |
| `pci_compliance_logs` | PCI compliance audit logs |

## API Endpoints

### Payments
- `POST /api/v1/payments/charge` - Process a payment charge
- `POST /api/v1/payments/authorize` - Authorize a payment
- `POST /api/v1/payments/{id}/capture` - Capture authorized payment
- `POST /api/v1/payments/{id}/void` - Void a payment
- `POST /api/v1/payments/{id}/refund` - Refund a payment
- `GET /api/v1/payments/{id}` - Get payment details
- `GET /api/v1/payments/` - List payments

### Payment Methods
- `POST /api/v1/payment-methods/` - Add payment method
- `GET /api/v1/payment-methods/{id}` - Get payment method
- `PATCH /api/v1/payment-methods/{id}` - Update payment method
- `DELETE /api/v1/payment-methods/{id}` - Remove payment method
- `GET /api/v1/payment-methods/customer/{id}` - List customer methods

### Subscriptions
- `POST /api/v1/subscriptions/` - Create subscription
- `GET /api/v1/subscriptions/{id}` - Get subscription
- `PATCH /api/v1/subscriptions/{id}` - Update subscription
- `POST /api/v1/subscriptions/{id}/cancel` - Cancel subscription
- `POST /api/v1/subscriptions/{id}/pause` - Pause subscription
- `POST /api/v1/subscriptions/{id}/resume` - Resume subscription

### Fraud Detection
- `POST /api/v1/fraud/rules` - Create fraud rule
- `GET /api/v1/fraud/rules` - List fraud rules
- `PATCH /api/v1/fraud/rules/{id}` - Update fraud rule
- `DELETE /api/v1/fraud/rules/{id}` - Delete fraud rule
- `GET /api/v1/fraud/alerts` - List fraud alerts
- `POST /api/v1/fraud/alerts/{id}/review` - Review alert

### Disputes
- `GET /api/v1/disputes/` - List disputes
- `GET /api/v1/disputes/{id}` - Get dispute details
- `POST /api/v1/disputes/{id}/evidence` - Submit evidence
- `POST /api/v1/disputes/{id}/accept` - Accept dispute
- `GET /api/v1/disputes/metrics` - Get dispute metrics

### Webhooks
- `POST /api/v1/webhooks/stripe/{venue_id}` - Stripe webhook handler
- `POST /api/v1/webhooks/square/{venue_id}` - Square webhook handler

## Events Published

The service publishes events to RabbitMQ for other services to consume:

| Event | Description |
|-------|-------------|
| `payment.completed` | Payment successfully processed |
| `payment.failed` | Payment processing failed |
| `payment.declined` | Payment declined by processor |
| `refund.completed` | Refund successfully processed |
| `subscription.created` | New subscription created |
| `subscription.cancelled` | Subscription cancelled |
| `subscription.renewed` | Subscription renewed |
| `fraud.alert_created` | New fraud alert triggered |
| `dispute.created` | New dispute/chargeback received |

## Key Metrics

| Metric | Target |
|--------|--------|
| Payment Success Rate | 98.7% |
| Fraud Detection Accuracy | 99.2% |
| Processing Time | < 2 seconds |
| Dispute Win Rate | > 70% |

## Security

- **PCI DSS Compliance**: Card data is never stored directly; only tokenized references
- **Encryption**: Sensitive data (API keys, tokens) encrypted at rest using Fernet
- **JWT Authentication**: All endpoints require valid JWT tokens
- **Webhook Verification**: All processor webhooks are signature-verified
- **Input Validation**: Comprehensive Pydantic validation on all inputs

## Quick Start

See [SETUP_GUIDE.md](./SETUP_GUIDE.md) for detailed setup instructions.

```bash
# Install dependencies
poetry install

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the service
uvicorn app.main:app --reload
```

## Testing

See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for detailed testing instructions.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `JWT_SECRET_KEY` | JWT signing secret | Required |
| `STRIPE_API_KEY` | Stripe secret key | Required for Stripe |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | Required for webhooks |
| `SQUARE_ACCESS_TOKEN` | Square access token | Required for Square |
| `ENCRYPTION_KEY` | Data encryption key | Required |
| `RABBITMQ_URL` | RabbitMQ connection string | Required |

## Dependencies

- **FastAPI**: Web framework
- **SQLAlchemy 2.0**: Async ORM
- **Stripe SDK**: Stripe integration
- **Square SDK**: Square integration
- **Cryptography**: Data encryption
- **aio-pika**: RabbitMQ client
- **python-jose**: JWT handling
- **structlog**: Structured logging

## License

Proprietary - FEC SaaS Platform
