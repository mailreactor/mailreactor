"""Structured logging configuration with console and JSON renderers.

This module provides a single internal pipeline with dual renderers:
- Console renderer (default): Human-readable colored output via rich integration
- JSON renderer (opt-in): Machine-readable structured logs for log aggregators

Usage:
    # Configure at application startup
    configure_logging(json_format=False, log_level="INFO")

    # Get a logger
    logger = structlog.get_logger()

    # Log with context
    logger.info("email_sent", recipient="user@example.com", message_id="abc123")

    # Bind context for request tracing
    bind_context(request_id="123e4567-e89b-12d3-a456-426614174000")
    logger.info("processing_email")  # request_id automatically included
    clear_context()
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


# Sensitive field names to redact from logs
SENSITIVE_FIELDS = {
    "password",
    "api_key",
    "auth_token",
    "secret",
    "authorization",
    "apikey",
    "api-key",
}


def _filter_sensitive_data(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact sensitive fields from log output.

    Args:
        logger: The wrapped logger instance
        method_name: The name of the method called (e.g., "info", "error")
        event_dict: The event dictionary to process

    Returns:
        Event dictionary with sensitive fields redacted
    """
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_FIELDS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(json_format: bool = False, log_level: str = "INFO") -> None:
    """Configure structlog with console or JSON renderer.

    Args:
        json_format: If True, use JSON renderer. If False, use console renderer.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Examples:
        >>> # Development mode with colored console output
        >>> configure_logging(json_format=False, log_level="INFO")
        >>>
        >>> # Production mode with JSON output
        >>> configure_logging(json_format=True, log_level="WARNING")
    """
    # Configure stdlib logging as backend
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        stream=sys.stderr,
    )

    # Shared processors (before renderer)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _filter_sensitive_data,
    ]

    # Choose renderer based on configuration
    if json_format:
        # Production: JSON Lines format
        # Note: format_exc_info must be absent for JSON to work with ConsoleRenderer
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Rich-enhanced console output
        # ConsoleRenderer handles exceptions itself, so don't use format_exc_info
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback,
            ),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to current structlog context.

    Context variables are automatically included in all subsequent log entries
    until they are unbound or cleared.

    Args:
        **kwargs: Key-value pairs to bind to the logging context

    Examples:
        >>> bind_context(request_id="abc-123", account_id="user@example.com")
        >>> logger.info("processing_request")  # Will include request_id and account_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove specific keys from structlog context.

    Args:
        *keys: Context keys to remove

    Examples:
        >>> unbind_context("request_id", "account_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables.

    This should be called at the end of request processing to ensure
    context doesn't leak between requests.

    Examples:
        >>> clear_context()  # Remove all bound context
    """
    structlog.contextvars.clear_contextvars()
