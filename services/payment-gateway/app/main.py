"""
=============================================================================
FILE: main.py
PURPOSE: FastAPI application entry point for Payment Gateway Service
=============================================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.api.v1 import payments, payment_methods, subscriptions, fraud, disputes, webhooks
from app.services.event_publisher import event_publisher

logger = structlog.get_logger()

# Database setup
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler."""
    # Startup
    logger.info("starting_payment_gateway_service", environment=settings.ENV)

    # Connect event publisher (non-blocking - service works without RabbitMQ)
    try:
        await event_publisher.connect()
    except Exception as e:
        logger.warning("event_publisher_connection_failed", error=str(e))

    yield

    # Shutdown
    logger.info("shutting_down_payment_gateway_service")
    try:
        await event_publisher.disconnect()
    except Exception:
        pass
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="Payment Gateway Service",
    description="""
    FEC SaaS Payment Gateway Service

    A comprehensive payment processing service that handles:
    - Payment processing (charge, authorize, capture, void)
    - Refund management
    - Subscription/recurring billing
    - Payment method management
    - Fraud detection and prevention
    - Dispute/chargeback handling
    - PCI compliance tracking

    Supports multiple payment processors:
    - Stripe
    - Square
    """,
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError as 400 Bad Request."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"},
    )


# Include routers
app.include_router(payments.router, prefix="/api/v1")
app.include_router(payment_methods.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(fraud.router, prefix="/api/v1")
app.include_router(disputes.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "payment-gateway"}


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Readiness check including database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "disconnected"},
        )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Payment Gateway Service",
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else "disabled",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
