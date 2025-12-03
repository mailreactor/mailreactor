"""FastAPI application initialization and configuration.

This module creates and configures the Mail Reactor FastAPI application with:
- Structured logging (configured first, before any other initialization)
- OpenAPI documentation (Swagger UI and ReDoc)
- CORS middleware (disabled by default)
- Custom exception handlers for MailReactorException hierarchy
- Request ID middleware for tracing
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mailreactor.api.dependencies import RequestIDMiddleware
from mailreactor.config import settings
from mailreactor.exceptions import MailReactorException
from mailreactor.utils.logging import configure_logging

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure FastAPI application instance.

    Returns:
        Configured FastAPI application with middleware and exception handlers

    Examples:
        >>> app = create_app()
        >>> app.title
        'Mail Reactor API'
    """
    # Configure logging FIRST (before any other operations)
    configure_logging(json_format=settings.json_logs, log_level=settings.log_level)

    logger.info(
        "server_starting",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )

    app = FastAPI(
        title="Mail Reactor API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Request ID middleware (NFR-O3: Request Tracing)
    app.add_middleware(RequestIDMiddleware)

    # CORS middleware (disabled by default for security)
    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Exception handlers
    @app.exception_handler(MailReactorException)  # type: ignore[misc]
    async def mailreactor_exception_handler(
        request: Request, exc: MailReactorException
    ) -> JSONResponse:
        """Handle custom MailReactorException with standard error envelope.

        Args:
            request: FastAPI request instance
            exc: MailReactorException instance

        Returns:
            JSONResponse with error code, message, and appropriate HTTP status
        """
        logger.warning(
            "mailreactor_exception",
            error_code=exc.__class__.__name__.upper(),
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.__class__.__name__.upper(),
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)  # type: ignore[misc]
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions with 500 Internal Server Error.

        Args:
            request: FastAPI request instance
            exc: Generic exception instance

        Returns:
            JSONResponse with generic error message and 500 status
        """
        logger.error(
            "internal_server_error",
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )

    return app


# Module-level app instance for uvicorn entry point
app = create_app()
