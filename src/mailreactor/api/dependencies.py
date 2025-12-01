"""FastAPI dependencies and middleware.

This module provides shared FastAPI dependencies including:
- Request ID middleware for request tracing (NFR-O3)
- Future: API key authentication
- Future: State management dependencies
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Middleware to generate unique request IDs for tracing.

    Generates a UUID for each request and injects it into:
    - Response headers as X-Request-ID
    - Request state for access by endpoints
    - Future: structlog context for log correlation (Story 1.3)

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

        # TODO (Story 1.3): Bind request_id to structlog context
        # structlog.contextvars.bind_contextvars(request_id=request_id)

        # Process request
        response = await call_next(request)

        # Inject request ID into response headers
        response.headers["X-Request-ID"] = request_id

        return response
