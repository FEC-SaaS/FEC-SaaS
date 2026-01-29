"""Restaurant Service entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.services.event_publisher import event_publisher

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("starting_restaurant_service", env=settings.ENV)
    try:
        await event_publisher.connect()
    except Exception as e:
        logger.warning("event_publisher_connection_failed", error=str(e))
    yield
    try:
        await event_publisher.disconnect()
    except Exception as e:
        logger.warning("event_publisher_disconnect_error", error=str(e))
    logger.info("restaurant_service_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.VERSION}
