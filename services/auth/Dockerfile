# =============================================================================
# FEC SaaS Auth Service - Production Multi-Stage Dockerfile
# =============================================================================
# This Dockerfile follows best practices for production Python applications:
# - Multi-stage build to minimize final image size
# - Non-root user for security
# - Health checks for container orchestration
# - Proper layer caching for faster builds
# - Security hardening
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and build wheels
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /build

# Copy dependency files first for better layer caching
COPY pyproject.toml poetry.lock* ./

# Export dependencies to requirements.txt and install
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS production

# Labels for container metadata
LABEL maintainer="FEC SaaS Team" \
      version="0.1.0" \
      description="Auth & User Management Service for FEC SaaS" \
      org.opencontainers.image.source="https://github.com/fec-saas/auth-service"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    # App-specific
    APP_HOME=/app \
    APP_USER=appuser \
    APP_GROUP=appgroup \
    # Default settings (override in deployment)
    AUTH_ENV=production \
    AUTH_DEBUG=false \
    PORT=8000

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user for security
RUN groupadd --gid 1000 ${APP_GROUP} \
    && useradd --uid 1000 --gid ${APP_GROUP} --shell /bin/bash --create-home ${APP_USER}

# Set working directory
WORKDIR ${APP_HOME}

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY --chown=${APP_USER}:${APP_GROUP} ./app ${APP_HOME}/app
COPY --chown=${APP_USER}:${APP_GROUP} ./alembic ${APP_HOME}/alembic
COPY --chown=${APP_USER}:${APP_GROUP} ./alembic.ini ${APP_HOME}/alembic.ini

# Create directory for logs (if needed)
RUN mkdir -p ${APP_HOME}/logs \
    && chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}

# Switch to non-root user
USER ${APP_USER}

# Expose port
EXPOSE ${PORT}

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/auth/health || exit 1

# Default command - run with gunicorn for production
# Using uvicorn workers for async support
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]

# -----------------------------------------------------------------------------
# Stage 3: Development - Includes dev dependencies
# -----------------------------------------------------------------------------
FROM production AS development

# Switch back to root for installing dev dependencies
USER root

# Install dev dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    isort \
    mypy \
    ruff \
    httpx

# Switch back to non-root user
USER ${APP_USER}

# Override command for development
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload"]
