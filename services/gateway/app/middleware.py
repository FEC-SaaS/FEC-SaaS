"""
=============================================================================
FILE: middleware.py
PURPOSE: API Gateway middleware components
=============================================================================

This module provides middleware components for the API Gateway including:
- Rate limiting
- Request logging
- Authentication validation
- Circuit breaker

MIDDLEWARE COMPONENTS:
1. RateLimitMiddleware - Throttles requests per client
2. RequestLoggingMiddleware - Logs all requests for monitoring
3. AuthenticationMiddleware - Validates JWT tokens
4. CircuitBreakerMiddleware - Prevents cascading failures

USAGE:
    from app.middleware import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

=============================================================================
"""

import time
import jwt
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.

    Limits requests per client IP address. Uses in-memory storage
    by default, can be configured to use Redis for distributed setups.

    Attributes:
        requests: Dict tracking request timestamps per client
        window_size: Time window in seconds
        max_requests: Maximum requests per window
    """

    def __init__(self, app, window_size: int = 60, max_requests: int = 100):
        super().__init__(app)
        self.requests: Dict[str, list] = defaultdict(list)
        self.window_size = window_size
        self.max_requests = max_requests

    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier (IP address)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _clean_old_requests(self, client_id: str, current_time: float):
        """Remove requests outside the current window."""
        cutoff = current_time - self.window_size
        self.requests[client_id] = [
            ts for ts in self.requests[client_id] if ts > cutoff
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_id = self._get_client_id(request)
        current_time = time.time()

        # Clean old requests
        self._clean_old_requests(client_id, current_time)

        # Check rate limit
        request_count = len(self.requests[client_id])

        if request_count >= self.max_requests:
            logger.warning(
                "rate_limit_exceeded",
                client=client_id,
                path=request.url.path,
                count=request_count,
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": self.window_size,
                },
                headers={
                    "Retry-After": str(self.window_size),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Record this request
        self.requests[client_id].append(current_time)

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.max_requests - len(self.requests[client_id])
        )

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Request logging middleware for monitoring and debugging.

    Logs all incoming requests with:
    - Method, path, query params
    - Client IP and user agent
    - Response status and timing
    - Request ID for tracing
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        request_id = getattr(request.state, "request_id", "unknown")
        start_time = time.time()

        # Log incoming request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query) if request.url.query else None,
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown")[:100],
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Log response
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )

        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware.

    Validates JWT tokens in the Authorization header for protected endpoints.
    Public endpoints are configured in settings.PUBLIC_PATHS.

    Note: This middleware only validates the token signature and expiration.
    Fine-grained authorization is handled by individual services.
    """

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        for public_path in settings.PUBLIC_PATHS:
            if path.startswith(public_path):
                return True
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    def _validate_token(self, token: str) -> Optional[dict]:
        """Validate JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            # Check token type
            if payload.get("type") != "access":
                return None

            # Check expiration (jwt.decode handles this, but explicit check)
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(
                timezone.utc
            ):
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("token_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug("token_invalid", error=str(e))
            return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate authentication for protected endpoints."""
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract token
        token = self._extract_token(request)
        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "Missing authentication token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        payload = self._validate_token(token)
        if not payload:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Store user info in request state for downstream use
        request.state.user_id = payload.get("sub")
        request.state.token_payload = payload

        return await call_next(request)


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Circuit breaker middleware for service resilience.

    Prevents cascading failures by tracking service errors and
    temporarily blocking requests to failing services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests immediately fail
    - HALF_OPEN: Testing if service recovered

    Attributes:
        failures: Dict tracking failure counts per service
        last_failure: Dict tracking last failure time per service
        state: Dict tracking circuit state per service
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, app):
        super().__init__(app)
        self.failures: Dict[str, int] = defaultdict(int)
        self.last_failure: Dict[str, float] = {}
        self.state: Dict[str, str] = defaultdict(lambda: self.CLOSED)

    def _get_service_key(self, path: str) -> str:
        """Extract service key from path."""
        parts = path.split("/")
        if len(parts) >= 4:
            return parts[3]  # e.g., 'auth' from '/api/v1/auth/...'
        return "unknown"

    def _should_allow_request(self, service: str) -> bool:
        """Check if request should be allowed based on circuit state."""
        state = self.state[service]

        if state == self.CLOSED:
            return True

        if state == self.OPEN:
            # Check if recovery timeout has passed
            last_fail = self.last_failure.get(service, 0)
            if time.time() - last_fail > settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT:
                # Transition to half-open
                self.state[service] = self.HALF_OPEN
                return True
            return False

        if state == self.HALF_OPEN:
            # Allow one request to test
            return True

        return True

    def _record_success(self, service: str):
        """Record successful request."""
        if self.state[service] == self.HALF_OPEN:
            # Service recovered, close circuit
            self.state[service] = self.CLOSED
            self.failures[service] = 0
            logger.info("circuit_closed", service=service)

    def _record_failure(self, service: str):
        """Record failed request."""
        self.failures[service] += 1
        self.last_failure[service] = time.time()

        if self.failures[service] >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            self.state[service] = self.OPEN
            logger.warning(
                "circuit_opened",
                service=service,
                failures=self.failures[service],
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with circuit breaker."""
        if not settings.CIRCUIT_BREAKER_ENABLED:
            return await call_next(request)

        service = self._get_service_key(request.url.path)

        # Check circuit state
        if not self._should_allow_request(service):
            logger.warning(
                "circuit_open_rejected",
                service=service,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "service": service,
                },
            )

        # Process request
        response = await call_next(request)

        # Record result
        if response.status_code >= 500:
            self._record_failure(service)
        else:
            self._record_success(service)

        return response


# =============================================================================
# END OF FILE
# =============================================================================
