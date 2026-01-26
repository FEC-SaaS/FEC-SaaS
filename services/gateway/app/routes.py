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
- /api/v1/venues/* → Venue Service
- /api/v1/parties/* → Party Service
- /api/v1/customers/* → Customer Service
- /api/v1/bookings/* → Booking Service
- /api/v1/payments/* → Payment Service
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
    - Managing notification templates
    - User notification preferences
    - Notification history and status
    """
    return await proxy_request(
        request,
        settings.NOTIFICATION_SERVICE_URL,
        f"/api/v1/notifications/{path}",
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
    - Visit history
    - Loyalty program
    - Customer preferences
    """
    return await proxy_request(
        request,
        settings.CUSTOMER_SERVICE_URL,
        f"/api/v1/customers/{path}",
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
    - Payment methods
    - Transaction history
    """
    return await proxy_request(
        request,
        settings.PAYMENT_SERVICE_URL,
        f"/api/v1/payments/{path}",
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

    Handles all analytics endpoints including:
    - Revenue reports
    - Customer analytics
    - Venue performance
    - Booking trends
    """
    return await proxy_request(
        request,
        settings.ANALYTICS_SERVICE_URL,
        f"/api/v1/analytics/{path}",
    )


# =============================================================================
# END OF FILE
# =============================================================================
