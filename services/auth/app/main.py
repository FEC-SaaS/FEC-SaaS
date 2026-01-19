"""FEC SaaS Auth Service - Main Application Entry Point.

This module initializes the FastAPI application with all middleware,
routers, and lifecycle events.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.redis import get_redis_client, close_redis_connection
from app.db.session import Base, engine
from app.middleware.security import SecurityHeadersMiddleware, RequestIdMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app import models  # noqa: F401  - ensure models imported for metadata

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENV != "production" else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events handler."""
    # Startup
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENV} environment")

    # Initialize database tables (development only)
    if settings.ENV == "local":
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created (local mode)")

    # Test Redis connection
    redis_client = get_redis_client()
    if redis_client:
        logger.info("Redis connection established")
    else:
        logger.warning("Redis not available - rate limiting and token blacklist will use fallback")

    yield

    # Shutdown
    logger.info("Shutting down application")
    close_redis_connection()


# Enable docs for non-production environments
_enable_docs = settings.ENV in ("local", "dev", "development", "staging") or settings.DEBUG

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Auth & User Management Service for FEC SaaS Platform",
    version="0.1.0",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter

# Register rate limit error handler
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add middleware (order matters - last added is first executed)
# 1. Security headers (outermost - runs last on response)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request ID tracing
app.add_middleware(RequestIdMiddleware)

# 3. CORS (must be before route handling)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint - service status."""
    return {"service": "auth", "status": "ok", "version": "0.1.0"}


@app.get("/health", tags=["health"])
async def root_health_check():
    """Root health check endpoint."""
    redis_status = "connected" if get_redis_client() else "not_configured"
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
        "redis": redis_status,
    }


@app.get("/api/v1/auth/health", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestration."""
    redis_status = "connected" if get_redis_client() else "not_configured"
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": "0.1.0",
            "redis": redis_status,
        },
    )


@app.get("/api/v1/auth/ready", tags=["health"])
async def readiness_check():
    """Readiness check endpoint - verifies database and Redis connectivity."""
    from sqlalchemy import text
    from app.db.session import SessionLocal

    status = {"database": "unknown", "redis": "unknown"}
    all_ready = True

    # Check database
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        all_ready = False

    # Check Redis (optional but recommended)
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.ping()
            status["redis"] = "connected"
        except Exception:
            status["redis"] = "error"
            # Redis is optional, don't fail readiness
    else:
        status["redis"] = "not_configured"

    if all_ready:
        return JSONResponse(
            status_code=200,
            content={"status": "ready", **status},
        )
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", **status},
        )


app.include_router(api_router, prefix=settings.API_V1_STR)

