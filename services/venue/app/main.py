"""
=============================================================================
FILE: main.py
PURPOSE: FastAPI application entry point for Venue Service
=============================================================================
"""

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.api.v1 import router as api_v1_router
from app.core.cache import cache_manager
from app.core.events import event_publisher
from app.core.rate_limit import rate_limiter, rate_limit_middleware

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler for startup and shutdown."""
    logger.info("venue_service_starting", version=settings.app_version)

    # Database setup
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    app.state.engine = engine
    app.state.async_session = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    # Initialize Redis-based features
    if settings.ENABLE_CACHING:
        await cache_manager.connect()
        logger.info("caching_enabled")

    if settings.ENABLE_EVENT_PUBLISHING:
        await event_publisher.connect()
        logger.info("event_publishing_enabled")

    if settings.ENABLE_RATE_LIMITING:
        await rate_limiter.connect()
        logger.info("rate_limiting_enabled")

    logger.info("venue_service_started")

    yield

    # Shutdown
    logger.info("venue_service_shutting_down")

    if settings.ENABLE_CACHING:
        await cache_manager.disconnect()

    if settings.ENABLE_EVENT_PUBLISHING:
        await event_publisher.disconnect()

    if settings.ENABLE_RATE_LIMITING:
        await rate_limiter.disconnect()

    await engine.dispose()
    logger.info("venue_service_stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Venue Management Service for FEC SaaS Platform - Multi-location franchise management with AI-powered features",
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

# Include API routers
app.include_router(api_v1_router)


@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "venue",
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "FEC Venue Service",
        "version": settings.app_version,
        "documentation": "/docs" if settings.debug else "disabled",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
