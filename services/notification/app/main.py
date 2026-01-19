"""FastAPI application entry point for Notification Service."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.redis import close_redis_connection, get_redis_client

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    redis_client = get_redis_client()
    if redis_client:
        print("Redis connected successfully")
    else:
        print("Warning: Redis not configured - queue features will be limited")

    yield

    # Shutdown
    close_redis_connection()


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Email & SMS Notification microservice for FEC SaaS",
    version="0.1.0",
    docs_url="/docs" if settings.ENV in ["local", "development", "staging"] else None,
    redoc_url="/redoc" if settings.ENV in ["local", "development", "staging"] else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENV in ["local", "development", "staging"] else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    redis_client = get_redis_client()

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENV,
        "redis": "connected" if redis_client else "not_configured",
    }
