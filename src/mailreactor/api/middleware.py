"""FastAPI middleware components.

This module provides HTTP middleware including:
- Request ID middleware for request tracing (NFR-O3)
- Request timing and logging
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from mailreactor.utils.logging import bind_context, clear_context

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Middleware to generate unique request IDs for tracing.

    Generates a UUID for each request and injects it into:
    - Response headers as X-Request-ID
    - Request state for access by endpoints
    - Structlog context for log correlation

    This implements NFR-O3 (Request Tracing) for operational observability.

    Examples:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(RequestIDMiddleware)
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Generate request ID and inject into request/response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            Response with X-Request-ID header
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Store in request state for endpoint access
        request.state.request_id = request_id

        # Bind request_id to structlog context
        bind_context(request_id=request_id)

        # Track request timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration (use float for sub-millisecond precision)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            # Classify request type for filtering/metrics
            path = str(request.url.path)
            request_type = "api" if path.startswith("/api/") else "static"

            # Log request completion
            logger.info(
                "http_request",
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_type=request_type,
            )

            # Inject request ID into response headers
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Clean up context after request (prevent context leakage)
            clear_context()
