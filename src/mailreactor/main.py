"""FastAPI application initialization and configuration.

This module creates and configures the Mail Reactor FastAPI application with:
- OpenAPI documentation (Swagger UI and ReDoc)
- CORS middleware (disabled by default)
- Custom exception handlers for MailReactorException hierarchy
- Request ID middleware for tracing

Note: Logging is configured by the CLI before calling create_app().
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from mailreactor.api.health import router as health_router
from mailreactor.api.middleware import RequestIDMiddleware
from mailreactor.config import settings
from mailreactor.exceptions import MailReactorException
from mailreactor.models.responses import ErrorDetail, ErrorResponse
from mailreactor.utils.version import get_app_version

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
    app = FastAPI(
        title="Mail Reactor API",
        description="""
## Welcome to Mail Reactor API

Send and receive emails via REST API using your IMAP/SMTP accounts.

### What You Can Do

- **Send emails** - Plain text, HTML, attachments, multiple recipients
- **Retrieve emails** - Search your inbox using IMAP syntax
- **Manage accounts** - Connect Gmail, Outlook, Yahoo, or any IMAP/SMTP server

Thanks for using Mail Reactor!
        """,
        version=get_app_version(),
        contact={
            "name": "Mail Reactor Project",
            "url": "https://github.com/mailreactor/mailreactor",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
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

    # Register routers
    app.include_router(health_router)  # Mounts at root level /health

    # Favicon endpoint (envelope emoji)
    @app.get("/favicon.ico", include_in_schema=False)  # type: ignore[misc]
    async def favicon() -> Response:
        """Serve envelope emoji as favicon.

        Returns SVG favicon for browser tab display.
        """
        # SVG with envelope emoji - works across all modern browsers
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <text y="80" font-size="80">⚛️</text>
        </svg>"""
        return Response(content=svg_content, media_type="image/svg+xml")

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
            JSONResponse with ErrorResponse model and appropriate HTTP status
        """
        logger.warning(
            "mailreactor_exception",
            error_code=exc.__class__.__name__.upper(),
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.__class__.__name__.upper(),
                    message=exc.message,
                    details=None,
                )
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)  # type: ignore[misc]
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI validation errors with field-specific details.

        Args:
            request: FastAPI request instance
            exc: RequestValidationError from Pydantic validation

        Returns:
            JSONResponse with ErrorResponse model and 400 status
        """
        logger.warning("validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Invalid request parameters",
                    details={"errors": exc.errors()},
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)  # type: ignore[misc]
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions with 500 Internal Server Error.

        Args:
            request: FastAPI request instance
            exc: Generic exception instance

        Returns:
            JSONResponse with ErrorResponse model and 500 status
        """
        logger.error(
            "internal_server_error",
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected error occurred",
                    details=None,
                )
            ).model_dump(),
        )

    return app
