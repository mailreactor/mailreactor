"""Structured logging configuration with console and JSON renderers.

This module provides a single internal pipeline with dual renderers:
- Console renderer (default): Human-readable colored output via rich integration
- JSON renderer (opt-in): Machine-readable structured logs for log aggregators

PII Protection:
    Sensitive data is automatically protected via structlog processor:
    - Passwords, tokens, secrets: Fully redacted as [REDACTED]
    - Email addresses: Masked to show only domain (***@example.com)

    This happens automatically - no need to manually mask at log sites.

Usage:
    # Configure at application startup
    configure_logging(json_format=False, log_level="INFO")

    # Get a logger
    logger = structlog.get_logger()

    # Log with context (PII auto-masked)
    logger.info("email_sent", recipient="user@example.com")  # → recipient=***@example.com
    logger.info("auth", password="secret")  # → password=[REDACTED]  # pragma: allowlist secret

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
    "password",  # pragma: allowlist secret
    "api_key",
    "auth_token",
    "secret",  # pragma: allowlist secret
    "authorization",
    "apikey",
    "api-key",
    "token",
    "bearer",
}

# PII field names to mask (not fully redact)
PII_FIELDS = {
    "email",
    "recipient",
    "sender",
}


def _mask_email(email: str) -> str:
    """Mask email address for PII-safe logging.

    Args:
        email: Email address to mask

    Returns:
        Masked email with username replaced by ***

    Examples:
        >>> _mask_email("user@example.com")
        '***@example.com'
        >>> _mask_email("invalid")
        '***'
    """
    if not isinstance(email, str):
        return str(email)

    parts = email.split("@")
    if len(parts) == 2:
        return f"***@{parts[1]}"
    return "***"


def _filter_sensitive_data(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact sensitive fields and mask PII from log output.

    This processor automatically protects sensitive information:
    - Sensitive fields (passwords, tokens): Fully redacted as [REDACTED]
    - PII fields (emails): Masked to show only domain (***@domain.com)

    Args:
        logger: The wrapped logger instance
        method_name: The name of the method called (e.g., "info", "error")
        event_dict: The event dictionary to process

    Returns:
        Event dictionary with sensitive fields redacted and PII masked

    Examples:
        >>> # These transformations happen automatically:
        >>> logger.info("event", password="secret123")  # pragma: allowlist secret
        >>> # → password=[REDACTED]
        >>> logger.info("event", email="user@example.com")  # → email=***@example.com
    """
    for key in list(event_dict.keys()):
        key_lower = key.lower()

        # Fully redact sensitive fields
        if key_lower in SENSITIVE_FIELDS:
            event_dict[key] = "[REDACTED]"

        # Mask PII fields (emails)
        elif key_lower in PII_FIELDS and isinstance(event_dict[key], str):
            event_dict[key] = _mask_email(event_dict[key])

    return event_dict


def configure_logging(json_format: bool = False, log_level: str = "INFO") -> None:
    """Configure structlog with console or JSON renderer.

    This also configures Python's standard logging (used by Uvicorn and other
    libraries) to use structlog's formatting, ensuring consistent log output.

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
    # Shared processors used by both structlog and stdlib loggers (before renderer)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _filter_sensitive_data,
    ]

    # Choose renderer based on configuration
    renderer = (
        structlog.processors.JSONRenderer()
        if json_format
        else structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.rich_traceback,
        )
    )

    # Configure structlog with stdlib integration
    # Note: structlog loggers use these processors + wrap_for_formatter
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,  # Reuse shared processors
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure Python's standard logging to use structlog's formatting
    # This makes Uvicorn and other libraries use structlog formatting
    # Note: foreign_pre_chain processes stdlib logs before passing to renderer
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))


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
