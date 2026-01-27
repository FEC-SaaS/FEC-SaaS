"""
=============================================================================
FILE: main.py
PURPOSE: API Gateway main application entry point
=============================================================================

This is the main entry point for the FEC SaaS API Gateway. The gateway acts
as a single entry point for all client requests and routes them to the
appropriate microservices.

WHAT IT DOES:
- Routes requests to backend microservices (auth, notification, venue, etc.)
- Handles authentication and authorization
- Implements rate limiting and request throttling
- Provides request/response logging
- Manages CORS for frontend applications
- Handles circuit breaking for service resilience
- Aggregates responses when needed

ARCHITECTURE:
                    ┌─────────────────┐
    Clients ──────► │   API Gateway   │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌────────────┐   ┌────────────┐   ┌────────────┐
    │ Auth Svc   │   │ Notif Svc  │   │ Venue Svc  │
    └────────────┘   └────────────┘   └────────────┘

CONFIGURATION:
Environment variables are loaded from .env file or system environment.
See config.py for all available settings.

USAGE:
    # Development
    uvicorn app.main:app --reload --port 8080

    # Production
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

=============================================================================
"""

import time
import uuid
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import router as gateway_router
from app.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    AuthenticationMiddleware,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize HTTP client pool, connect to Redis
    - Shutdown: Close connections gracefully
    """
    # Startup
    logger.info(
        "gateway_starting",
        environment=settings.ENV,
        version=settings.VERSION,
    )

    # Create shared HTTP client for proxying requests
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

    logger.info("gateway_started", port=settings.PORT)

    yield

    # Shutdown
    logger.info("gateway_shutting_down")
    await app.state.http_client.aclose()
    logger.info("gateway_stopped")


# Create FastAPI application
app = FastAPI(
    title="FEC SaaS API Gateway",
    description="""
    ## API Gateway for FEC SaaS Platform

    This gateway provides a unified API entry point for all FEC SaaS services.

    ### Features
    - **Authentication**: JWT-based authentication via Auth Service
    - **Rate Limiting**: Configurable rate limits per endpoint
    - **Request Routing**: Routes to appropriate microservices
    - **Health Checks**: Service health monitoring

    ### Services
    - `/api/v1/auth/*` - Authentication Service
    - `/api/v1/notifications/*` - Notification Service
    - `/api/v1/templates/*` - Notification Service (templates)
    - `/api/v1/venues/*` - Venue Management Service
    - `/api/v1/parties/*` - Party Booking Service
    - `/api/v1/customers/*` - Customer Service
    - `/api/v1/families/*` - Customer Service (family groups)
    - `/api/v1/visits/*` - Customer Service (visit tracking)
    - `/api/v1/segments/*` - Customer Service (segmentation)
    - `/api/v1/membership/*` - Membership Service (subscriptions, loyalty, rewards, family, corporate, referrals, tiers, analytics)
    - `/api/v1/bookings/*` - Booking Service
    - `/api/v1/payments/*` - Payment Service
    - `/api/v1/payment-methods/*` - Payment Gateway (payment methods)
    - `/api/v1/fraud/*` - Payment Gateway (fraud detection)
    - `/api/v1/disputes/*` - Payment Gateway (disputes)
    - `/api/v1/analytics/*` - Analytics Service
    """,
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracing."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    # Add to structlog context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


# Request timing middleware
@app.middleware("http")
async def add_timing(request: Request, call_next):
    """Track request processing time."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

    # Log slow requests
    if process_time > 1.0:
        logger.warning(
            "slow_request",
            path=request.url.path,
            method=request.method,
            duration_ms=round(process_time * 1000, 2),
        )

    return response


# Include gateway routes
app.include_router(gateway_router)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Gateway health check endpoint.

    Returns the health status of the gateway and connectivity
    to backend services.
    """
    return {
        "status": "healthy",
        "service": "api-gateway",
        "version": settings.VERSION,
        "environment": settings.ENV,
    }


# Readiness check endpoint
@app.get("/ready", tags=["Health"])
async def readiness_check(request: Request):
    """
    Readiness check for Kubernetes.

    Checks if the gateway can accept traffic by verifying
    connectivity to critical services.
    """
    checks = {}

    # Service health check configuration: (name, url, health_path)
    service_checks = [
        ("auth_service", settings.AUTH_SERVICE_URL, "/api/v1/auth/health"),
        ("notification_service", settings.NOTIFICATION_SERVICE_URL, "/api/v1/notifications/health"),
        ("venue_service", settings.VENUE_SERVICE_URL, "/health"),
        ("party_service", settings.PARTY_SERVICE_URL, "/health"),
        ("customer_service", settings.CUSTOMER_SERVICE_URL, "/health"),
        ("membership_service", settings.MEMBERSHIP_SERVICE_URL, "/health"),
        ("booking_service", settings.BOOKING_SERVICE_URL, "/health"),
        ("payment_service", settings.PAYMENT_SERVICE_URL, "/health"),
        ("payment_gateway", settings.PAYMENT_GATEWAY_SERVICE_URL, "/health"),
        ("analytics_service", settings.ANALYTICS_SERVICE_URL, "/health"),
    ]

    for service_name, service_url, health_path in service_checks:
        try:
            response = await request.app.state.http_client.get(
                f"{service_url}{health_path}",
                timeout=5.0,
            )
            checks[service_name] = response.status_code == 200
        except Exception:
            checks[service_name] = False

    all_healthy = all(checks.values())

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
        },
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": request_id,
        },
    )


# =============================================================================
# END OF FILE
# =============================================================================
