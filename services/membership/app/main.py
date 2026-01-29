"""
=============================================================================
FILE: main.py
PURPOSE: FastAPI application entry point for Membership Service
=============================================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import init_db, close_db
from app.services.event_publisher import event_publisher
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    print(f"Starting {settings.service_name}...")

    # Initialize database
    if settings.environment == "development":
        await init_db()
        print("Database initialized")

    # Connect to RabbitMQ
    try:
        await event_publisher.connect()
        print("Connected to RabbitMQ")
    except Exception as e:
        print(f"Warning: Could not connect to RabbitMQ: {e}")

    yield

    # Shutdown
    print(f"Shutting down {settings.service_name}...")
    await event_publisher.disconnect()
    await close_db()


app = FastAPI(
    title="Membership Service",
    description="""
    Comprehensive membership management service for FEC SaaS platform.

    ## Features

    - **Subscription Management**: Create and manage subscription plans, handle billing cycles
    - **Loyalty Programs**: Points earning, redemption, tier management
    - **Rewards Catalog**: Manage rewards and track redemptions
    - **Family Memberships**: Shared family plans with points pooling
    - **Corporate Subscriptions**: B2B subscription management with employee tracking
    - **Referral Program**: Customer referrals with reward tracking
    - **Analytics**: MRR, churn, LTV, and other key metrics

    ## Key Metrics Targets

    - Reduce churn from 68% to 31%
    - Increase LTV from $340 to $1,240
    - Achieve 87% subscription retention
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred",
            "type": type(exc).__name__,
        },
    )


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Readiness check for Kubernetes."""
    # Could add database connectivity check here
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"status": "alive"}


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
