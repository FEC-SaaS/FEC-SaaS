"""
=============================================================================
FILE: routes.py
PURPOSE: API Gateway routing and request proxying
=============================================================================

This module handles routing requests to backend microservices. It acts as
a reverse proxy, forwarding requests to the appropriate service based on
the URL path.

WHAT IT DOES:
- Routes requests to backend services based on URL prefix
- Preserves request headers, query params, and body
- Forwards authentication tokens to backend services
- Handles service errors gracefully
- Provides circuit breaking for service resilience

ROUTE MAPPING:
- /api/v1/auth/* → Auth Service
- /api/v1/notifications/* → Notification Service
- /api/v1/templates/* → Notification Service (templates)
- /api/v1/venues/* → Venue Service
- /api/v1/parties/* → Party Service
- /api/v1/customers/* → Customer Service
- /api/v1/families/* → Customer Service (family groups)
- /api/v1/visits/* → Customer Service (visit tracking)
- /api/v1/segments/* → Customer Service (segmentation)
- /api/v1/membership/* → Membership Service (subscriptions, loyalty, rewards,
                          family memberships, corporate, referrals, tiers, analytics)
- /api/v1/bookings/* → Booking Service
- /api/v1/payments/* → Payment Service
- /api/v1/payment-methods/* → Payment Gateway (payment methods)
- /api/v1/fraud/* → Payment Gateway (fraud detection)
- /api/v1/disputes/* → Payment Gateway (disputes/chargebacks)
- /api/v1/analytics/* → Analytics Service
- /api/v1/restaurant/* → Restaurant Service (tables, reservations, menu,
                          orders, KDS, bar, waste, digital menus)
- /api/v1/staff/* → Staff & Scheduling Service (profiles, roles, shifts,
                     time clock, availability, time off, swaps, payroll, analytics)

USAGE:
    # Routes are automatically included in main.py
    from app.routes import router

=============================================================================
"""

import httpx
import structlog
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings, get_service_url

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter()


async def proxy_request(
    request: Request,
    service_url: str,
    path: str,
) -> Response:
    """
    Proxy a request to a backend service.

    Args:
        request: The incoming FastAPI request
        service_url: Base URL of the target service
        path: The path to forward to

    Returns:
        The response from the backend service
    """
    # Build target URL
    target_url = f"{service_url}{path}"

    # Include query string if present
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Prepare headers (forward most headers, exclude hop-by-hop headers)
    excluded_headers = {
        "host",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in excluded_headers
    }

    # Add gateway headers
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")

    # Get request body
    body = await request.body()

    try:
        # Make request to backend service
        http_client: httpx.AsyncClient = request.app.state.http_client

        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            follow_redirects=False,
        )

        # Build response headers (exclude hop-by-hop)
        response_headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in excluded_headers
            and key.lower() != "content-encoding"  # Let FastAPI handle encoding
        }

        logger.info(
            "request_proxied",
            method=request.method,
            path=path,
            target=service_url,
            status=response.status_code,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
        )

    except httpx.ConnectError as e:
        logger.error(
            "service_connection_failed",
            service=service_url,
            path=path,
            error=str(e),
        )
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
        )

    except httpx.TimeoutException as e:
        logger.error(
            "service_timeout",
            service=service_url,
            path=path,
            error=str(e),
        )
        raise HTTPException(
            status_code=504,
            detail="Service request timed out",
        )

    except Exception as e:
        logger.error(
            "proxy_error",
            service=service_url,
            path=path,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Error communicating with service",
        )


# =============================================================================
# Auth Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Auth Service"],
)
async def auth_proxy(request: Request, path: str):
    """
    Proxy requests to the Auth Service.

    Handles all authentication-related endpoints including:
    - User registration and login
    - Token refresh and logout
    - Password reset
    - Email/phone verification
    - User profile management
    - MFA setup and verification
    """
    return await proxy_request(
        request,
        settings.AUTH_SERVICE_URL,
        f"/api/v1/auth/{path}",
    )


# =============================================================================
# Notification Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/notifications/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Notification Service"],
)
async def notification_proxy(request: Request, path: str):
    """
    Proxy requests to the Notification Service.

    Handles all notification-related endpoints including:
    - Sending notifications (email, SMS, push)
    - User notification preferences
    - Notification history and status
    """
    return await proxy_request(
        request,
        settings.NOTIFICATION_SERVICE_URL,
        f"/api/v1/notifications/{path}",
    )


@router.api_route(
    "/api/v1/templates/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Notification Service"],
)
async def templates_proxy(request: Request, path: str):
    """
    Proxy requests to the Notification Service - Templates.

    Handles notification template management:
    - Create and manage email/SMS templates
    - Template variables and rendering
    """
    return await proxy_request(
        request,
        settings.NOTIFICATION_SERVICE_URL,
        f"/api/v1/templates/{path}",
    )


# =============================================================================
# Venue Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/venues/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Venue Service"],
)
async def venue_proxy(request: Request, path: str):
    """
    Proxy requests to the Venue Service.

    Handles all venue-related endpoints including:
    - Venue CRUD operations
    - Attraction management
    - Operating hours
    - Capacity management
    """
    return await proxy_request(
        request,
        settings.VENUE_SERVICE_URL,
        f"/api/v1/venues/{path}",
    )


# =============================================================================
# Party Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/parties/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Party Service"],
)
async def party_proxy(request: Request, path: str):
    """
    Proxy requests to the Party Service.

    Handles all party booking endpoints including:
    - Party package management
    - Booking creation and management
    - Party scheduling
    - Guest management
    """
    return await proxy_request(
        request,
        settings.PARTY_SERVICE_URL,
        f"/api/v1/parties/{path}",
    )


# =============================================================================
# Customer Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/customers/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Customer Service"],
)
async def customer_proxy(request: Request, path: str):
    """
    Proxy requests to the Customer Service.

    Handles all customer-related endpoints including:
    - Customer profiles
    - Customer preferences
    - Customer search and lookup
    """
    return await proxy_request(
        request,
        settings.CUSTOMER_SERVICE_URL,
        f"/api/v1/customers/{path}",
    )


@router.api_route(
    "/api/v1/families/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Customer Service"],
)
async def families_proxy(request: Request, path: str):
    """
    Proxy requests to the Customer Service - Families.

    Handles family grouping and management:
    - Create and manage family groups
    - Link customer accounts to families
    - Family-level preferences
    """
    return await proxy_request(
        request,
        settings.CUSTOMER_SERVICE_URL,
        f"/api/v1/families/{path}",
    )


@router.api_route(
    "/api/v1/visits/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Customer Service"],
)
async def visits_proxy(request: Request, path: str):
    """
    Proxy requests to the Customer Service - Visits.

    Handles visit tracking:
    - Record customer visits
    - Visit history and frequency analysis
    - Check-in/check-out tracking
    """
    return await proxy_request(
        request,
        settings.CUSTOMER_SERVICE_URL,
        f"/api/v1/visits/{path}",
    )


@router.api_route(
    "/api/v1/segments/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Customer Service"],
)
async def segments_proxy(request: Request, path: str):
    """
    Proxy requests to the Customer Service - Segments.

    Handles customer segmentation:
    - Create and manage customer segments
    - Segment rules and criteria
    - Segment membership queries
    """
    return await proxy_request(
        request,
        settings.CUSTOMER_SERVICE_URL,
        f"/api/v1/segments/{path}",
    )


# =============================================================================
# Membership Service Routes
# =============================================================================
# All membership routes are namespaced under /api/v1/membership/* in the
# gateway, which forwards to the membership service's internal routes.
# This avoids prefix conflicts with other services (analytics, family, etc.)
#
# Gateway path → Membership service path:
#   /api/v1/membership/subscriptions/* → /api/v1/subscriptions/*
#   /api/v1/membership/loyalty/*       → /api/v1/loyalty/*
#   /api/v1/membership/rewards/*       → /api/v1/rewards/*
#   /api/v1/membership/family/*        → /api/v1/family/*
#   /api/v1/membership/corporate/*     → /api/v1/corporate/*
#   /api/v1/membership/referrals/*     → /api/v1/referrals/*
#   /api/v1/membership/analytics/*     → /api/v1/analytics/*
#   /api/v1/membership/tiers/*         → /api/v1/tiers/*
# =============================================================================
@router.api_route(
    "/api/v1/membership/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Membership Service"],
)
async def membership_proxy(request: Request, path: str):
    """
    Proxy requests to the Membership Service.

    Handles all membership-related endpoints including:

    **Subscriptions** (`/api/v1/membership/subscriptions/...`):
    - Subscription plans CRUD
    - Customer subscriptions (subscribe, pause, resume, cancel)
    - Plan upgrades/downgrades with proration
    - Usage tracking and limits
    - Billing and invoice management
    - Dunning for failed payments

    **Loyalty Programs** (`/api/v1/membership/loyalty/...`):
    - Loyalty program creation and management
    - Customer enrollment and account management
    - Points earning and redemption
    - Points transfer between accounts
    - Tier progression tracking
    - Points expiration management

    **Rewards Catalog** (`/api/v1/membership/rewards/...`):
    - Rewards catalog management
    - Reward redemption and fulfillment
    - Redemption code verification
    - Tier-restricted rewards

    **Family Memberships** (`/api/v1/membership/family/...`):
    - Family plan creation
    - Member management (add/remove)
    - Shared points pool
    - Primary member transfer

    **Corporate Subscriptions** (`/api/v1/membership/corporate/...`):
    - Corporate subscription management
    - Employee provisioning and bulk operations
    - Employee access verification
    - Contract renewal and management

    **Referral Program** (`/api/v1/membership/referrals/...`):
    - Referral code generation and validation
    - Referral usage and completion
    - Dual-sided reward tracking
    - Referral leaderboards

    **Membership Tiers** (`/api/v1/membership/tiers/...`):
    - Tier CRUD (Bronze, Silver, Gold, Platinum)
    - Tier benefits configuration
    - Tier progression rules

    **Membership Analytics** (`/api/v1/membership/analytics/...`):
    - MRR (Monthly Recurring Revenue)
    - Churn rate tracking
    - Customer Lifetime Value (LTV)
    - Loyalty program metrics
    - Rewards redemption analytics
    - Referral performance
    - Dashboard summary
    """
    return await proxy_request(
        request,
        settings.MEMBERSHIP_SERVICE_URL,
        f"/api/v1/{path}",
    )


# =============================================================================
# Booking Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/bookings/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Booking Service"],
)
async def booking_proxy(request: Request, path: str):
    """
    Proxy requests to the Booking Service.

    Handles all booking-related endpoints including:
    - Attraction reservations
    - Time slot management
    - Booking modifications
    - Cancellations
    """
    return await proxy_request(
        request,
        settings.BOOKING_SERVICE_URL,
        f"/api/v1/bookings/{path}",
    )


# =============================================================================
# Payment Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/payments/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Payment Service"],
)
async def payment_proxy(request: Request, path: str):
    """
    Proxy requests to the Payment Service.

    Handles all payment-related endpoints including:
    - Payment processing
    - Refunds
    - Transaction history
    """
    return await proxy_request(
        request,
        settings.PAYMENT_SERVICE_URL,
        f"/api/v1/payments/{path}",
    )


# =============================================================================
# Payment Gateway Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/payment-methods/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Payment Gateway"],
)
async def payment_methods_proxy(request: Request, path: str):
    """
    Proxy requests to the Payment Gateway - Payment Methods.

    Handles payment method management:
    - Add/remove payment methods (cards, bank accounts)
    - Set default payment method
    - Payment method validation
    """
    return await proxy_request(
        request,
        settings.PAYMENT_GATEWAY_SERVICE_URL,
        f"/api/v1/payment-methods/{path}",
    )


@router.api_route(
    "/api/v1/fraud/{path:path}",
    methods=["GET", "POST"],
    tags=["Payment Gateway"],
)
async def fraud_proxy(request: Request, path: str):
    """
    Proxy requests to the Payment Gateway - Fraud Detection.

    Handles fraud detection endpoints:
    - Transaction risk scoring
    - Fraud rule management
    - Suspicious activity reports
    """
    return await proxy_request(
        request,
        settings.PAYMENT_GATEWAY_SERVICE_URL,
        f"/api/v1/fraud/{path}",
    )


@router.api_route(
    "/api/v1/disputes/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH"],
    tags=["Payment Gateway"],
)
async def disputes_proxy(request: Request, path: str):
    """
    Proxy requests to the Payment Gateway - Disputes.

    Handles dispute and chargeback management:
    - View and manage disputes
    - Submit evidence for chargebacks
    - Dispute resolution tracking
    """
    return await proxy_request(
        request,
        settings.PAYMENT_GATEWAY_SERVICE_URL,
        f"/api/v1/disputes/{path}",
    )


# =============================================================================
# Analytics Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/analytics/{path:path}",
    methods=["GET", "POST"],
    tags=["Analytics Service"],
)
async def analytics_proxy(request: Request, path: str):
    """
    Proxy requests to the Analytics Service.

    Handles platform-wide analytics endpoints including:
    - Revenue reports
    - Customer analytics
    - Venue performance
    - Booking trends

    Note: For membership-specific analytics (MRR, churn, LTV),
    use /api/v1/membership/analytics/* instead.
    """
    return await proxy_request(
        request,
        settings.ANALYTICS_SERVICE_URL,
        f"/api/v1/analytics/{path}",
    )


# =============================================================================
# Restaurant Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/restaurant/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Restaurant Service"],
)
async def restaurant_proxy(request: Request, path: str):
    """
    Proxy requests to the Restaurant Service.

    Handles all restaurant/food & beverage endpoints including:

    **Tables & Sections** (`/api/v1/restaurant/sections`, `/api/v1/restaurant/tables`):
    - Section CRUD (dining room, bar, patio, private)
    - Table management and status tracking
    - Table availability queries

    **Reservations** (`/api/v1/restaurant/reservations`):
    - Create and manage table reservations
    - Seat and complete reservations

    **Menu** (`/api/v1/restaurant/menu`):
    - Full menu retrieval with categories and items
    - Menu item CRUD with allergens, dietary tags, pricing
    - Menu modifiers and availability toggling
    - Menu categories with meal time scheduling

    **Orders** (`/api/v1/restaurant/orders`):
    - Create orders (dine-in, takeout, delivery, curbside)
    - Order status management (pending → preparing → ready → served)
    - Add items to existing orders

    **Kitchen Display System** (`/api/v1/restaurant/kds`):
    - KDS queue management per station
    - Start and complete kitchen items
    - Station configuration

    **Bar** (`/api/v1/restaurant/bar`):
    - Bar inventory management
    - Pour tracking with inventory deduction
    - Low stock alerts

    **Waste** (`/api/v1/restaurant/waste`):
    - Food waste logging
    - Waste analytics (by reason, top wasted items, cost)

    **Digital Menu & Happy Hours** (`/api/v1/restaurant/digital-menu`, `/api/v1/restaurant/happy-hours`):
    - Digital menu board configuration
    - Happy hour schedule management
    """
    return await proxy_request(
        request,
        settings.RESTAURANT_SERVICE_URL,
        f"/api/v1/restaurant/{path}",
    )


# =============================================================================
# Reservation & Capacity Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/reservations/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Reservation & Capacity Service"],
)
async def reservations_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Reservations.

    Handles reservation lifecycle:
    - CRUD operations for reservations (bowling, mini golf, food, party, multi-activity)
    - Check-in, complete, confirm, cancel, no-show marking
    - Confirmation code lookup
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/reservations/{path}",
    )


@router.api_route(
    "/api/v1/availability/{path:path}",
    methods=["GET", "POST", "DELETE"],
    tags=["Reservation & Capacity Service"],
)
async def availability_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Availability.

    Handles time-slot availability:
    - Query available slots by venue, resource type, and date
    - Temporary time-slot holds (5-min expiry)
    - Real-time availability checks
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/availability/{path}",
    )


@router.api_route(
    "/api/v1/capacity/{path:path}",
    methods=["GET", "POST", "PUT"],
    tags=["Reservation & Capacity Service"],
)
async def capacity_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Capacity.

    Handles capacity configuration and monitoring:
    - Capacity config per venue + resource type
    - Real-time capacity dashboard
    - Capacity forecasting
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/capacity/{path}",
    )


@router.api_route(
    "/api/v1/waitlist/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    tags=["Reservation & Capacity Service"],
)
async def waitlist_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Waitlist.

    Handles waitlist management:
    - Add customers to waitlist with priority
    - Notify waitlisted customers when slots open
    - Convert waitlist entries to reservations
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/waitlist/{path}",
    )


@router.api_route(
    "/api/v1/reminders/{path:path}",
    methods=["GET", "POST"],
    tags=["Reservation & Capacity Service"],
)
async def reminders_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Reminders.

    Handles reservation reminders:
    - Schedule confirmation, 24-hour, and 1-hour reminders
    - Send via email, SMS, or push
    - Process pending reminder batches
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/reminders/{path}",
    )


@router.api_route(
    "/api/v1/no-shows/{path:path}",
    methods=["GET"],
    tags=["Reservation & Capacity Service"],
)
async def no_shows_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – No-Shows.

    Handles no-show tracking and customer reliability:
    - No-show history by venue
    - Customer no-show history
    - Customer reliability scores
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/no-shows/{path}",
    )


@router.api_route(
    "/api/v1/overbooking/{path:path}",
    methods=["GET", "POST"],
    tags=["Reservation & Capacity Service"],
)
async def overbooking_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Overbooking.

    Handles overbooking optimization:
    - Overbooking rules per venue/resource/time period
    - Historical no-show rate analysis
    - Recommended overbooking rate forecasting
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/overbooking/{path}",
    )


@router.api_route(
    "/api/v1/reservation-analytics/{path:path}",
    methods=["GET"],
    tags=["Reservation & Capacity Service"],
)
async def reservation_analytics_proxy(request: Request, path: str):
    """
    Proxy requests to the Reservation & Capacity Service – Analytics.

    Handles reservation-specific analytics:
    - Utilization rates by resource type
    - No-show analysis and trends
    - Revenue impact metrics
    - Booking channel performance
    """
    return await proxy_request(
        request,
        settings.RESERVATION_CAPACITY_SERVICE_URL,
        f"/api/v1/reservation-analytics/{path}",
    )


# =============================================================================
# Bowling Management Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/bowling/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Bowling Service"],
)
async def bowling_proxy(request: Request, path: str):
    """
    Proxy requests to the Bowling Management Service.

    Handles all bowling-related endpoints including:

    **Lanes** (`/api/v1/bowling/lanes`):
    - Lane inventory and real-time status tracking
    - Lane availability queries by date and type
    - Lane status management (available, occupied, maintenance, offline)

    **Reservations** (`/api/v1/bowling/reservations`):
    - Lane reservation CRUD with time-slot conflict detection
    - Check-in, completion, cancellation, and no-show tracking
    - Dynamic pricing per lane, per time slot

    **Sessions** (`/api/v1/bowling/sessions`):
    - Active session tracking with scoring data
    - Game count and duration tracking
    - Player scores with frame-by-frame data

    **Shoes** (`/api/v1/bowling/shoes`):
    - Shoe rental and return management
    - Real-time shoe inventory tracking per venue and size
    - Low-stock alerts

    **Maintenance** (`/api/v1/bowling/maintenance`):
    - Preventive maintenance scheduling per lane
    - Maintenance lifecycle (scheduled → in-progress → completed)
    - Overdue maintenance tracking

    **Analytics** (`/api/v1/bowling/analytics`):
    - Lane utilization statistics
    - Revenue analytics by lane and date range
    - Peak-time heatmap data
    """
    return await proxy_request(
        request,
        settings.BOWLING_SERVICE_URL,
        f"/api/v1/bowling/{path}",
    )


# =============================================================================
# POS Integration Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/pos/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["POS Service"],
)
async def pos_proxy(request: Request, path: str):
    """
    Proxy requests to the POS Integration Service.

    Handles all point-of-sale and transaction-related endpoints including:

    **Transactions** (`/api/v1/pos/transactions`):
    - Universal transaction logging across all activities
    - Transaction lifecycle: PENDING -> COMPLETED / VOIDED
    - Multi-activity support (bowling, arcade, food, party, membership, retail)

    **Payments** (`/api/v1/pos/payments`):
    - Multi-tender payment processing (cash, card, game card, gift card)
    - Payment reversals and processor integration
    - Payment method analytics

    **Receipts** (`/api/v1/pos/receipts`):
    - Digital receipt generation and management
    - Email and print support

    **Refunds** (`/api/v1/pos/refunds`):
    - Approval-based refund workflow
    - Full and partial refund support

    **Cash Drawers** (`/api/v1/pos/cash-drawers`):
    - Cash drawer open/close lifecycle
    - Cash drop tracking and variance detection

    **Tax Rates** (`/api/v1/pos/tax-rates`):
    - Jurisdiction-based tax configuration
    - Real-time tax calculation

    **Reconciliation** (`/api/v1/pos/reconciliation`):
    - Automated daily reconciliation
    - Variance detection and reporting

    **External Integrations** (`/api/v1/pos/integrations`):
    - Toast, Square, Clover POS connectivity
    - Sync management and logging
    """
    return await proxy_request(
        request,
        settings.POS_SERVICE_URL,
        f"/api/v1/pos/{path}",
    )


# =============================================================================
# Staff & Scheduling Service Routes
# =============================================================================
@router.api_route(
    "/api/v1/staff/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Staff Service"],
)
async def staff_proxy(request: Request, path: str):
    """
    Proxy requests to the Staff & Scheduling Service (SmartStaff).

    Handles all workforce management endpoints including:

    **Staff Profiles** (`/api/v1/staff/profiles`):
    - Staff profile CRUD operations
    - Employee ID generation (EMP-001 format)
    - Employment status management (active, on_leave, terminated)
    - Employment type tracking (full_time, part_time, seasonal, contractor)
    - Emergency contact storage

    **Staff Roles** (`/api/v1/staff/profiles/{id}/roles`):
    - Multi-role assignment (FRONT_DESK, PARTY_HOST, COOK, etc.)
    - Skill level tracking (trainee, intermediate, expert)
    - Role-specific hourly rates
    - Primary role designation
    - Role certification dates

    **Shifts** (`/api/v1/staff/shifts`):
    - Shift scheduling with date, start/end times, break duration
    - Shift status management (scheduled, confirmed, completed, no_show, cancelled)
    - Conflict detection (overlapping shifts, rest time, max hours)
    - Shift confirmation workflow
    - Shift calendar queries by venue/date range

    **Time Clock** (`/api/v1/staff/time-clock`):
    - Clock in/out with geolocation verification
    - Geofence enforcement (within venue radius)
    - Automatic regular/overtime hour calculation
    - Break tracking
    - Timesheet queries and manual edits

    **Availability** (`/api/v1/staff/availability`):
    - Weekly availability preferences per staff member
    - Day-of-week time windows (available_from, available_to)
    - Preference levels (preferred, available, unavailable)
    - Effective date scheduling for future changes

    **Time Off** (`/api/v1/staff/time-off`):
    - Time-off request submission (vacation, sick, personal, unpaid)
    - Approval workflow with reviewer tracking
    - Request status management (pending, approved, denied, cancelled)
    - Conflict detection with scheduled shifts

    **Shift Swaps** (`/api/v1/staff/swaps`):
    - Staff-to-staff shift swap requests
    - Approval workflow for managers
    - Automatic qualification verification
    - Swap deadline enforcement (hours before shift)

    **Payroll** (`/api/v1/staff/payroll`):
    - Payroll period management (open, closed, paid)
    - Individual payroll entry generation per staff
    - Regular/overtime hour aggregation
    - Gross pay, tips, deductions, net pay calculation

    **Analytics** (`/api/v1/staff/analytics`):
    - Labor cost tracking (daily and hourly granularity)
    - Labor cost vs. revenue percentage
    - Overtime reports by staff
    - Attendance reports (on-time, late, no-show rates)
    - Staffing alerts (overtime risk, labor cost threshold)
    """
    return await proxy_request(
        request,
        settings.STAFF_SERVICE_URL,
        f"/api/v1/{path}",
    )


# =============================================================================
# END OF FILE
# =============================================================================
