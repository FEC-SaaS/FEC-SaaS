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
# END OF FILE
# =============================================================================
