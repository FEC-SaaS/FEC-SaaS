# Customer Service

Customer management microservice for the FEC SaaS platform. Handles customer profiles, families, visits, segmentation, analytics, and churn prediction.

## Features

- **Customer Management**: Full CRUD for customer profiles (B2C/B2B)
- **Family Grouping**: Link related customers together with roles
- **Visit Tracking**: Record customer visits with activities and spending
- **Segmentation**: Automatic customer segmentation (VIP, Premium, Standard, At-Risk, New, Churned, Inactive)
- **LTV Calculation**: Customer lifetime value tracking and prediction
- **Churn Risk**: Predict customer churn risk with scoring
- **Analytics**: Comprehensive customer analytics dashboard
- **GDPR Compliance**: Support for data deletion requests

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with async SQLAlchemy 2.0
- **Cache**: Redis
- **Validation**: Pydantic v2
- **Migrations**: Alembic

## API Endpoints

### Customers (`/api/v1/customers`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List customers with filtering |
| POST | `/` | Create new customer |
| GET | `/search` | Search customers |
| GET | `/at-risk` | Get at-risk customers |
| GET | `/{id}` | Get customer details |
| PUT | `/{id}` | Update customer |
| DELETE | `/{id}` | Delete customer (soft/GDPR) |
| GET | `/{id}/preferences` | Get customer preferences |
| POST | `/{id}/preferences` | Add preference |
| POST | `/{id}/winback` | Trigger win-back campaign |
| POST | `/recalculate-segments` | Recalculate all segments |

### Families (`/api/v1/families`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List families |
| POST | `/` | Create family |
| GET | `/{id}` | Get family |
| PUT | `/{id}` | Update family |
| DELETE | `/{id}` | Delete family |
| POST | `/{id}/members` | Add family member |
| DELETE | `/{id}/members/{member_id}` | Remove member |

### Visits (`/api/v1/visits`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List visits with filters |
| POST | `/` | Create visit (check-in) |
| GET | `/{id}` | Get visit details |
| PUT | `/{id}` | Update visit |
| PATCH | `/{id}/checkout` | Check out visit |
| POST | `/{id}/activities` | Add activity |
| GET | `/customer/{id}` | Get customer visits |
| GET | `/stats` | Get visit statistics |

### Segments (`/api/v1/segments`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{type}/customers` | Get customers by segment |
| GET | `/customer/{id}` | Get customer segment |
| POST | `/assign` | Assign segment |
| POST | `/customer/{id}/recalculate` | Recalculate segment |
| GET | `/stats` | Get segment stats |

### Analytics (`/api/v1/analytics`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard` | Get analytics dashboard |
| GET | `/customer/{id}/ltv` | Get customer LTV |
| GET | `/customer/{id}/churn-risk` | Get churn risk |
| GET | `/customer/{id}/next-visit` | Get next visit prediction |
| GET | `/revenue` | Get revenue analytics |
| GET | `/churn` | Get churn analytics |
| GET | `/segments` | Get segment analytics |

## Data Models

### Customer Types
- `individual` - B2C customer
- `corporate` - B2B customer (company/organization)

### Segment Types
- `vip` - Highest value customers
- `premium` - High value customers
- `standard` - Regular customers
- `at_risk` - Showing signs of churn
- `new` - Recently acquired
- `churned` - No recent activity
- `inactive` - Minimal engagement

### Risk Levels
- `low` - Risk score < 0.25
- `medium` - Risk score 0.25-0.50
- `high` - Risk score 0.50-0.75
- `critical` - Risk score > 0.75

### Visit Sources
- `walk_in` - Walk-in customer
- `reservation` - From reservation
- `online_booking` - Online booking
- `party_booking` - Party booking
- `corporate_event` - Corporate event
- `membership` - Membership visit

### Activity Types
- `attraction` - Rides, games, activities
- `food_beverage` - Food and drinks
- `arcade` - Arcade games
- `merchandise` - Gift shop purchases
- `party` - Party services
- `other` - Other activities

## Configuration

Environment variables (see `.env.example`):

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/customer_db

# Redis
REDIS_URL=redis://localhost:6379/4

# Service
SERVICE_NAME=customer-service
SERVICE_PORT=8004

# Auth
JWT_SECRET=your-secret-key

# Segmentation Thresholds
VIP_LTV_THRESHOLD=1000.0
VIP_VISIT_THRESHOLD=20
PREMIUM_LTV_THRESHOLD=500.0
PREMIUM_VISIT_THRESHOLD=10
```

## Development

### Setup
```bash
# Install dependencies
poetry install

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8004
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_customer_service.py

# Run integration tests only
pytest tests/integration/
```

### Docker
```bash
# Build image
docker build -t customer-service .

# Run container
docker run -p 8004:8004 --env-file .env customer-service
```

## Segmentation Algorithm

Customers are automatically segmented based on:

1. **Total Revenue** (LTV)
2. **Visit Frequency**
3. **Recency** (days since last visit)
4. **Engagement Score**

Segmentation is recalculated:
- On visit checkout
- On scheduled batch job
- On manual trigger

## Churn Prediction

Churn risk is calculated using:
- Days since last visit
- Visit frequency decline
- Spending pattern changes
- Engagement score

Risk factors are weighted and combined into a single risk score (0-1).

## Health Check

```bash
curl http://localhost:8004/health
```

Response:
```json
{
  "status": "healthy",
  "service": "customer-service",
  "version": "1.0.0"
}
```
