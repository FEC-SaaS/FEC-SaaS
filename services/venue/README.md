# FEC Venue Service

Multi-location venue management service for the FEC SaaS Platform. Handles venue CRUD operations, operating hours, feature management, AI service configuration, performance tracking, and onboarding workflows.

## Features

- **Venue Management**: Create, read, update, delete venues with full location and contact details
- **Operating Hours**: Regular hours and special hours (holidays, events)
- **Feature Management**: Tier-based feature flags (STARTER, PRO, ENTERPRISE)
- **AI Service Configuration**: Per-venue AI service enablement and parameter tuning
- **Performance Tracking**: Revenue, guest counts, satisfaction metrics, and benchmarking
- **Onboarding Workflow**: Step-by-step venue activation process
- **Multi-tenant**: Franchise and multi-venue support

## API Endpoints

### Venues
- `GET /api/v1/venues` - List venues with filters and pagination
- `POST /api/v1/venues` - Create new venue
- `GET /api/v1/venues/{venue_id}` - Get venue details
- `PUT /api/v1/venues/{venue_id}` - Update venue
- `DELETE /api/v1/venues/{venue_id}` - Delete venue
- `GET /api/v1/venues/franchise/{franchise_id}` - List franchise venues
- `POST /api/v1/venues/bulk` - Bulk create venues
- `PATCH /api/v1/venues/bulk` - Bulk update venues

### Hours
- `GET /api/v1/venues/{venue_id}/hours` - Get regular hours
- `PUT /api/v1/venues/{venue_id}/hours` - Set regular hours
- `PATCH /api/v1/venues/{venue_id}/hours/{day}` - Update specific day
- `GET /api/v1/venues/{venue_id}/is-open` - Check if venue is open
- `GET /api/v1/venues/{venue_id}/hours/special` - Get special hours
- `POST /api/v1/venues/{venue_id}/hours/special` - Create special hours

### Settings
- `GET /api/v1/venues/{venue_id}/settings` - Get all settings
- `GET /api/v1/venues/{venue_id}/settings/{key}` - Get specific setting
- `POST /api/v1/venues/{venue_id}/settings/{key}` - Create/update setting
- `PUT /api/v1/venues/{venue_id}/settings` - Bulk update settings

### Features
- `GET /api/v1/venues/{venue_id}/features` - Get enabled features
- `GET /api/v1/venues/{venue_id}/features/available` - Get available features for tier
- `POST /api/v1/venues/{venue_id}/features/{name}` - Toggle feature
- `PUT /api/v1/venues/{venue_id}/features` - Bulk toggle features

### AI Configuration
- `GET /api/v1/venues/{venue_id}/ai-config` - Get AI service configs
- `GET /api/v1/venues/{venue_id}/ai-config/available` - Get available AI services
- `POST /api/v1/venues/{venue_id}/ai-config/{service}` - Enable AI service
- `PATCH /api/v1/venues/{venue_id}/ai-config/{service}` - Update config
- `DELETE /api/v1/venues/{venue_id}/ai-config/{service}` - Disable AI service

### Performance
- `GET /api/v1/venues/{venue_id}/performance` - Get performance history
- `POST /api/v1/venues/{venue_id}/performance` - Record performance snapshot
- `GET /api/v1/venues/{venue_id}/performance/summary` - Get aggregated summary
- `GET /api/v1/venues/{venue_id}/performance/compare` - Compare with other venues
- `GET /api/v1/venues/franchise/{id}/performance/leaderboard` - Franchise leaderboard

### Onboarding
- `GET /api/v1/venues/{venue_id}/onboarding` - Get onboarding status
- `POST /api/v1/venues/{venue_id}/onboarding/start` - Start onboarding
- `PATCH /api/v1/venues/{venue_id}/onboarding/step/{name}` - Update step
- `POST /api/v1/venues/{venue_id}/onboarding/complete` - Complete onboarding

## Subscription Tiers

| Feature | STARTER | PRO | ENTERPRISE |
|---------|---------|-----|------------|
| Bowling | ✓ | ✓ | ✓ |
| Arcade | ✓ | ✓ | ✓ |
| POS | ✓ | ✓ | ✓ |
| Reservations | ✓ | ✓ | ✓ |
| Food & Beverage | | ✓ | ✓ |
| Mini Golf | | ✓ | ✓ |
| Parties | | ✓ | ✓ |
| Loyalty | | ✓ | ✓ |
| Laser Tag | | ✓ | ✓ |
| Escape Rooms | | | ✓ |
| VR | | | ✓ |
| Go Karts | | | ✓ |
| Karaoke | | | ✓ |
| VIP Lanes | | | ✓ |
| League Management | | | ✓ |
| Pro Shop | | | ✓ |
| Dynamic Pricing AI | | ✓ | ✓ |
| Smart Staffing AI | | | ✓ |
| Churn Prediction AI | | | ✓ |
| Demand Forecasting AI | | | ✓ |
| Sentiment Analysis AI | | | ✓ |
| Inventory Optimization AI | | | ✓ |

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis (optional, for caching)

### Local Development

```bash
# Navigate to service directory
cd services/venue

# Install dependencies
poetry install

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# 
poetry add asyncpg

# Run database migrations
poetry run alembic upgrade head

# Start the service
poetry run uvicorn app.main:app --reload --port 8002
```

### Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# Run migrations
docker-compose exec venue-service alembic upgrade head
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | FEC Venue Service | Service name |
| `DEBUG` | false | Enable debug mode |
| `PORT` | 8002 | Service port |
| `DATABASE_URL` | postgresql+asyncpg://... | PostgreSQL connection |
| `JWT_SECRET_KEY` | (required) | JWT signing key |
| `ALLOWED_ORIGINS` | localhost:3000,3001 | CORS origins |
| `REDIS_URL` | redis://localhost:6379/2 | Redis for caching |

## Project Structure

```
services/venue/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── venues.py
│   │       ├── hours.py
│   │       ├── settings.py
│   │       ├── features.py
│   │       ├── ai_config.py
│   │       ├── performance.py
│   │       └── onboarding.py
│   ├── core/
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── models/
│   │   ├── base.py
│   │   └── venue.py
│   ├── schemas/
│   │   └── venue.py
│   ├── services/
│   │   ├── venue_service.py
│   │   ├── hours_service.py
│   │   ├── settings_service.py
│   │   ├── feature_service.py
│   │   ├── ai_config_service.py
│   │   ├── performance_service.py
│   │   └── onboarding_service.py
│   ├── config.py
│   └── main.py
├── alembic/
│   └── versions/
├── tests/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Database Models

- **Venue** - Core venue entity with location, contact, and status
- **VenueHours** - Regular operating hours (day of week)
- **VenueSpecialHours** - Holiday/event hours (specific dates)
- **VenueSetting** - Key-value configuration store
- **VenueFeature** - Feature flags with config
- **VenueAIConfig** - AI service parameters
- **VenuePerformance** - Daily performance metrics
- **VenueContact** - Staff/management contacts
- **VenueImage** - Logo, hero, gallery images

## Integration

The venue service integrates with:
- **Auth Service** - JWT token validation
- **Notification Service** - Onboarding status emails
- **API Gateway** - Routes at `/api/v1/venues/*`
