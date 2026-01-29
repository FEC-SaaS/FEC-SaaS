# Reservation & Capacity Service

## Overview

Unified reservation and capacity management system for FEC (Family Entertainment Center) venues. Handles the full reservation lifecycle across all activity types including bowling, mini golf, dining, parties, and multi-activity packages. Provides real-time capacity tracking, waitlist management, automated reminders, no-show tracking, overbooking optimization, and analytics.

## Architecture

- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (async)
- **Database:** PostgreSQL 15+
- **Cache:** Redis 7+
- **Message Broker:** RabbitMQ 3.12+
- **Port:** 8012

## Features

### Core Features

- **Reservation Lifecycle** -- Create, update, confirm, check-in, cancel, and mark no-shows
- **Capacity Management** -- Configure and track real-time capacity per venue, activity, and time slot
- **Time Slot Availability** -- Query available slots with hold/release support for concurrent booking
- **Waitlist** -- Queue customers when slots are full; notify and convert when openings arise
- **Reminders** -- Schedule and send reservation reminders and confirmations via notification service
- **No-Show Tracking** -- Record no-shows, maintain customer history, and compute reliability scores
- **Overbooking Optimization** -- Rule-based overbooking with demand forecasting per activity type
- **Analytics** -- Utilization reports, no-show trends, revenue projections, and channel breakdowns

### Production-Readiness Features

- **Rate Limiting** -- Redis-based sliding window rate limiter with per-venue (30 req/min) and per-customer (10 req/min) limits. Falls back to an in-memory counter when Redis is unavailable, ensuring the service remains operational without Redis.
- **Input Validation** -- Comprehensive request validation including past date rejection, business hours enforcement (reservations must fall within venue operating hours), maximum party size limits, and advance booking window restrictions.
- **Idempotency Keys** -- Optional `idempotency_key` field on reservation creation requests. Keys are stored with a 24-hour TTL and prevent duplicate reservations when clients retry failed requests. If a matching key is found, the original reservation is returned instead of creating a duplicate.
- **Composite Database Indexes** -- Performance-optimized composite indexes on frequently queried column combinations: `(venue_id, date, status)`, `(venue_id, date, time_slot)`, `(customer_id, date)`, and others. These indexes support efficient filtering and conflict detection queries at scale.
- **Structured Error Responses** -- Consistent error response format across all endpoints using an `ErrorCode` enum with 25+ codes. Every error response follows the JSON shape `{"error_code": "...", "message": "...", "details": {...}}`, making it straightforward for clients to handle errors programmatically.
- **Recurring Reservations** -- Create reservation series on weekly, biweekly, or monthly schedules with up to 52 occurrences. Supports cancellation of all occurrences or only future occurrences from a given date. All reservations in a series share a `recurring_group_id`.
- **Group/Block Bookings** -- Corporate event and group booking support. Allows reserving multiple resources (lanes, tables, courts) in a single request with a party size up to 500. All reservations in a group share a `group_booking_id` for unified management.
- **Deposit/Payment Integration** -- Collect, refund, and forfeit deposits for reservations via the external payment service. Tracks deposit lifecycle status (pending, collected, refunded, forfeited) on each reservation and communicates with the payment service over HTTP.
- **Notification Integration** -- Sends reservation confirmation emails upon creation and processes scheduled reminders via the external notification service. Uses an HTTP client to communicate with the notification service for email delivery.
- **Conflict Detection** -- Prevents customer double-bookings by checking for overlapping reservations for the same customer. Also performs resource-level conflict checking to ensure the same lane, table, or court is not booked twice for the same time slot.

## Database Tables

| # | Table | Description |
|---|-------|-------------|
| 1 | `reservations` | Core reservation records with status, timing, and customer info |
| 2 | `reservation_items` | Line items linking a reservation to specific activities/resources |
| 3 | `capacity_config` | Per-venue, per-activity capacity limits and slot durations |
| 4 | `time_slot_availability` | Tracks remaining capacity for each time slot |
| 5 | `reservation_waitlist` | Queued customers waiting for slot openings |
| 6 | `reservation_reminders` | Scheduled reminder records with send status |
| 7 | `no_show_history` | Historical log of customer no-show events |
| 8 | `customer_reservation_stats` | Aggregated stats per customer (total, no-shows, cancellations) |
| 9 | `overbooking_rules` | Activity-level overbooking percentages and thresholds |
| 10 | `reservation_notes` | Internal notes attached to reservations |
| 11 | `time_slot_holds` | Temporary holds on time slots during booking flow |

## API Endpoints

Base path: `/api/v1`

### Reservations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reservations` | List reservations with filters (venue, date, status) |
| POST | `/reservations` | Create a new reservation |
| GET | `/reservations/{id}` | Get reservation details |
| PUT | `/reservations/{id}` | Update a reservation |
| POST | `/reservations/{id}/cancel` | Cancel a reservation |
| POST | `/reservations/{id}/check-in` | Check in a reservation |
| POST | `/reservations/{id}/no-show` | Mark reservation as no-show |
| POST | `/reservations/{id}/confirm` | Confirm a pending reservation |

### Recurring Reservations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/reservations/recurring` | Create a recurring reservation series (weekly/biweekly/monthly, max 52 occurrences) |
| GET | `/reservations/recurring/{group_id}` | Get all reservations in a recurring series |
| DELETE | `/reservations/recurring/{group_id}` | Cancel a recurring series (all or future-only) |

### Group/Block Bookings

| Method | Path | Description |
|--------|------|-------------|
| POST | `/reservations/group` | Create a group/block booking (corporate events, multi-resource, max 500 party size) |
| GET | `/reservations/group/{group_id}` | Get all reservations in a group booking |
| DELETE | `/reservations/group/{group_id}` | Cancel all reservations in a group booking |

### Deposits

| Method | Path | Description |
|--------|------|-------------|
| POST | `/reservations/{id}/deposit/collect` | Collect a deposit for a reservation via payment service |
| POST | `/reservations/{id}/deposit/refund` | Refund a previously collected deposit |
| POST | `/reservations/{id}/deposit/forfeit` | Forfeit a deposit (e.g., on no-show or late cancellation) |

### Availability

| Method | Path | Description |
|--------|------|-------------|
| GET | `/availability` | Get availability for a venue/date/activity |
| GET | `/availability/time-slots` | List available time slots |
| POST | `/availability/hold` | Place a temporary hold on a time slot |
| POST | `/availability/release-hold` | Release a previously held time slot |

### Capacity

| Method | Path | Description |
|--------|------|-------------|
| GET | `/capacity/configs` | List capacity configurations |
| POST | `/capacity/configs` | Create a capacity configuration |
| PUT | `/capacity/configs/{id}` | Update a capacity configuration |
| GET | `/capacity/real-time` | Get real-time capacity for a venue |
| GET | `/capacity/forecast` | Forecast capacity demand |

### Waitlist

| Method | Path | Description |
|--------|------|-------------|
| GET | `/waitlist` | List waitlist entries |
| POST | `/waitlist` | Add customer to waitlist |
| DELETE | `/waitlist/{id}` | Remove customer from waitlist |
| POST | `/waitlist/{id}/notify` | Notify waitlisted customer of opening |
| POST | `/waitlist/{id}/convert` | Convert waitlist entry to reservation |

### Reminders

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reminders` | List scheduled reminders |
| POST | `/reminders` | Schedule a reminder for a reservation |
| POST | `/reminders/{id}/send-confirmation` | Send a confirmation message |

### No-Shows

| Method | Path | Description |
|--------|------|-------------|
| GET | `/no-shows` | List no-show records |
| GET | `/no-shows/customer/{customer_id}` | Get no-show history for a customer |
| GET | `/no-shows/customer/{customer_id}/reliability-score` | Get customer reliability score |

### Overbooking

| Method | Path | Description |
|--------|------|-------------|
| GET | `/overbooking/rules` | List overbooking rules |
| PUT | `/overbooking/rules` | Create or update an overbooking rule |
| GET | `/overbooking/forecast` | Forecast overbooking impact |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/utilization` | Venue/activity utilization rates |
| GET | `/analytics/no-shows` | No-show trend analysis |
| GET | `/analytics/revenue` | Revenue projections from reservations |
| GET | `/analytics/channels` | Booking channel breakdown |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Service name | `FEC Reservation & Capacity Service` |
| `VERSION` | Service version | `0.1.0` |
| `ENV` | Environment | `development` |
| `DEBUG` | Debug mode | `true` |
| `PORT` | HTTP port | `8012` |
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) | `postgresql+asyncpg://postgres:password@localhost:5432/reservation_capacity_db` |
| `DATABASE_POOL_SIZE` | Connection pool size | `10` |
| `DATABASE_MAX_OVERFLOW` | Pool overflow limit | `20` |
| `DATABASE_ECHO` | Log SQL queries | `false` |
| `REDIS_URL` | Redis connection string (used for rate limiting and idempotency keys) | `redis://localhost:6379/7` |
| `RABBITMQ_URL` | RabbitMQ connection string | `amqp://guest:guest@localhost:5672/` |
| `JWT_SECRET_KEY` | JWT signing key (must match auth service) | -- |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `AUTH_SERVICE_URL` | Auth service base URL | `http://localhost:8000` |
| `NOTIFICATION_SERVICE_URL` | Notification service base URL (used for confirmation emails and reminders) | `http://localhost:8001` |
| `PAYMENT_SERVICE_URL` | Payment service base URL (used for deposit collect/refund/forfeit) | `http://localhost:8006` |
| `VENUE_SERVICE_URL` | Venue service base URL | `http://localhost:8002` |
| `CUSTOMER_SERVICE_URL` | Customer service base URL | `http://localhost:8004` |
| `RESTAURANT_SERVICE_URL` | Restaurant service base URL | `http://localhost:8009` |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["http://localhost:3000","http://localhost:3001","http://localhost:8080"]` |

## Quick Start

```bash
# Install dependencies
poetry install

# Run database migrations
alembic upgrade head

# Start the service
uvicorn app.main:app --host 0.0.0.0 --port 8012 --reload
```

The service will be available at `http://localhost:8012`. Interactive API docs are at `http://localhost:8012/docs`.
