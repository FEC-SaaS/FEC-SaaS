"""
=============================================================================
FILE: main.py
PURPOSE: FastAPI application entry point for Customer Service
=============================================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.api.v1 import customers, families, visits, segments, analytics

settings = get_settings()
logger = structlog.get_logger()


# Database engine and session factory
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.DATABASE_ECHO,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    logger.info(
        "starting_customer_service",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.ENV,
    )

    # Store session factory in app state
    app.state.async_session = AsyncSessionLocal

    yield

    # Cleanup
    await engine.dispose()
    logger.info("customer_service_shutdown")


# OpenAPI Tags metadata
tags_metadata = [
    {
        "name": "customers",
        "description": "Customer profile management - CRUD operations, search, and preferences.",
    },
    {
        "name": "families",
        "description": "Family grouping and management - Link related customers together.",
    },
    {
        "name": "visits",
        "description": "Visit tracking - Check-in, checkout, activities, and statistics.",
    },
    {
        "name": "segments",
        "description": "Customer segmentation - VIP, Premium, Standard, At-Risk, etc.",
    },
    {
        "name": "analytics",
        "description": "Customer analytics - LTV, churn risk, revenue, and dashboards.",
    },
]

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
# GuestIQ Customer Service

Customer management microservice for the FEC SaaS platform.

## Features

- **Customer Profiles**: Full CRUD for B2C and B2B customers
- **Family Grouping**: Link related customers with roles
- **Visit Tracking**: Record visits, activities, and spending
- **Segmentation**: Automatic customer segmentation (VIP, Premium, Standard, At-Risk)
- **LTV Calculation**: Customer lifetime value tracking and prediction
- **Churn Risk**: Predict customer churn with risk scoring
- **GDPR Compliance**: Support for data deletion requests

## Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <token>
```

## Event Publishing

This service publishes events to the notification service:
- `customer.created`, `customer.updated`, `customer.deleted`
- `visit.checked_in`, `visit.checked_out`
- `segment.changed`, `churn.risk_high`
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    contact={
        "name": "FEC SaaS Team",
        "email": "support@fecsaas.com",
    },
    license_info={
        "name": "Proprietary",
    },
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(
    customers.router,
    prefix="/api/v1/customers",
    tags=["customers"],
)
app.include_router(
    families.router,
    prefix="/api/v1/families",
    tags=["families"],
)
app.include_router(
    visits.router,
    prefix="/api/v1/visits",
    tags=["visits"],
)
app.include_router(
    segments.router,
    prefix="/api/v1/segments",
    tags=["segments"],
)
app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["analytics"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "documentation": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
