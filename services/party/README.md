# FEC Party Service

Production-ready microservice for managing party packages, bookings, corporate events, and timelines for Family Entertainment Centers.

## Overview

The Party Service is a core component of the FEC SaaS platform, handling:
- **Party Packages**: Configurable party offerings with pricing tiers
- **Add-ons**: Extras like pizza, cake, decorations, goodie bags
- **Bookings**: Full lifecycle from inquiry to completion
- **Corporate Events**: Team building, company parties with lead scoring
- **Timeline Management**: Activity scheduling for party hosts
- **Analytics**: Revenue tracking and performance metrics

## Tech Stack

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **Cache**: Redis (DB 3)
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Auth**: JWT token validation (from Auth Service)

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Poetry

### Installation

```bash
# Navigate to service directory
cd services/party

# Install dependencies
poetry install

# Copy environment file
cp .env.example .env

# Edit .env with your settings
# Important: Update DATABASE_URL and JWT_SECRET_KEY

# Create database
createdb party_db

# install pydantic-settings
poetry add pydantic-settings
poetry add asyncpg

# Run migrations
poetry run alembic upgrade head

# Start development server
poetry run uvicorn app.main:app --reload --port 8003
```

### Docker

```bash
# Build image
docker build -t fec-party-service .

# Run container
docker run -p 8003:8003 --env-file .env fec-party-service
```

## API Endpoints

### Party Packages (`/api/v1/packages`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all packages (with filters) |
| POST | `/` | Create new package |
| GET | `/{id}` | Get package details |
| PUT | `/{id}` | Update package |
| DELETE | `/{id}` | Delete package |
| GET | `/{id}/addons` | Get package add-ons |
| POST | `/{id}/addons/{addon_id}` | Link add-on to package |
| DELETE | `/{id}/addons/{addon_id}` | Unlink add-on |
| POST | `/{id}/clone` | Clone package |
| POST | `/{id}/toggle-active` | Toggle active status |

### Add-ons (`/api/v1/addons`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all add-ons |
| POST | `/` | Create new add-on |
| GET | `/{id}` | Get add-on details |
| PUT | `/{id}` | Update add-on |
| DELETE | `/{id}` | Delete add-on |
| GET | `/categories` | List add-on categories |
| GET | `/venue/{venue_id}` | Get venue's add-ons |

### Bookings (`/api/v1/bookings`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List bookings (with filters) |
| POST | `/` | Create new booking |
| GET | `/{id}` | Get booking details |
| PUT | `/{id}` | Update booking |
| DELETE | `/{id}` | Cancel booking |
| POST | `/{id}/confirm` | Confirm booking |
| POST | `/{id}/check-in` | Check-in party |
| POST | `/{id}/complete` | Mark as completed |
| POST | `/{id}/addons` | Add add-ons to booking |
| DELETE | `/{id}/addons/{addon_id}` | Remove add-on |
| GET | `/{id}/invoice` | Generate invoice |
| POST | `/check-availability` | Check time slot availability |
| GET | `/calendar` | Get calendar view |
| GET | `/upcoming` | Get upcoming bookings |

### Corporate Events (`/api/v1/corporate`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List corporate events |
| POST | `/` | Create corporate inquiry |
| GET | `/{id}` | Get event details |
| PUT | `/{id}` | Update event |
| POST | `/{id}/convert` | Convert to booking |
| POST | `/{id}/calculate-lead-score` | Calculate lead score |
| GET | `/leads` | Get qualified leads |
| GET | `/pipeline` | Get sales pipeline |

### Timeline (`/api/v1/timeline`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/booking/{booking_id}` | Get booking timeline |
| POST | `/booking/{booking_id}` | Create timeline entry |
| PUT | `/{id}` | Update timeline entry |
| DELETE | `/{id}` | Delete timeline entry |
| POST | `/booking/{booking_id}/auto-generate` | Auto-generate timeline |
| POST | `/{id}/complete` | Mark activity complete |
| GET | `/host/{host_id}/today` | Get host's daily schedule |

### Analytics (`/api/v1/analytics`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/revenue` | Revenue analytics |
| GET | `/bookings` | Booking statistics |
| GET | `/packages/performance` | Package performance |
| GET | `/addons/performance` | Add-on performance |
| GET | `/corporate/metrics` | Corporate event metrics |
| GET | `/hosts/performance` | Host performance |
| GET | `/dashboard` | Dashboard summary |

## Database Schema

### Tables
- `party_packages` - Party package definitions
- `party_addons` - Available add-ons
- `party_package_addons` - Package-addon relationships
- `party_bookings` - Party reservations
- `party_booking_addons` - Booking add-on selections
- `corporate_events` - Corporate event inquiries/bookings
- `party_timeline` - Activity schedules
- `party_host_assignments` - Host-booking assignments

### Key Enums
- `PackageType`: STANDARD, PREMIUM, VIP, CUSTOM
- `PartyStatus`: INQUIRY, PENDING, CONFIRMED, CHECKED_IN, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW
- `AddonCategory`: FOOD, BEVERAGE, DECORATION, ENTERTAINMENT, FAVOR, SERVICE, OTHER
- `CorporateEventType`: TEAM_BUILDING, COMPANY_PARTY, CORPORATE_OUTING, PRIVATE_RENTAL, OTHER

## Configuration

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | - | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/3` | Redis connection (DB 3) |
| `JWT_SECRET_KEY` | - | Must match Auth Service |
| `PORT` | `8003` | Service port |
| `DEFAULT_PARTY_DURATION_MINUTES` | `120` | Default party length |
| `MIN_BOOKING_ADVANCE_HOURS` | `24` | Minimum advance booking |
| `MAX_BOOKING_ADVANCE_DAYS` | `365` | Maximum advance booking |
| `DEFAULT_DEPOSIT_PERCENTAGE` | `25.0` | Default deposit % |
| `ENABLE_AI_UPSELLS` | `true` | Enable AI recommendations |
| `ENABLE_AUTO_TIMELINE` | `true` | Enable auto timeline |

## Redis Database Allocation

| Service | Redis DB |
|---------|----------|
| Auth | 0 |
| Notification | 1 |
| Venue | 2 |
| **Party** | **3** |
| Customer | 4 |
| Payment | 5 |

## Integration Points

- **Auth Service** (8000): JWT validation, user info
- **Venue Service** (8002): Room availability, venue details
- **Notification Service** (8001): Email/SMS confirmations
- **Customer Service** (8004): Customer profiles
- **Payment Service** (8006): Payment processing

## Development

### Running Tests
```bash
poetry run pytest
poetry run pytest --cov=app --cov-report=html
```

### Code Quality
```bash
poetry run black app/
poetry run isort app/
poetry run flake8 app/
poetry run mypy app/
```

### Creating Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Completion Status: 85%

### Implemented
- Complete data models (8 tables)
- All Pydantic schemas (30+)
- Service layer with business logic
- REST API endpoints (45+)
- JWT authentication
- Configuration management
- Docker support
- Alembic migrations setup

### Needed for 100%
- [ ] Unit tests (pytest)
- [ ] Integration tests
- [ ] Event publishing (to message queue)
- [ ] Background task processing (Celery/ARQ)
- [ ] AI-powered upsell recommendations
- [ ] Advanced caching strategies
- [ ] Rate limiting implementation
- [ ] OpenAPI documentation enhancements
- [ ] Health check endpoints
- [ ] Metrics/monitoring (Prometheus)

## License

Proprietary - FEC SaaS Platform
