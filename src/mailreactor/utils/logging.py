"""Structured logging configuration with console and JSON renderers.

This module provides a single internal pipeline with dual renderers:
- Console renderer (default): Human-readable colored output via rich integration
- JSON renderer (opt-in): Machine-readable structured logs for log aggregators

All logs use structlog's structured format internally with shared processors
for timestamps, log levels, stack info, and exception formatting.

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
from rich.console import Console
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

# Emoji mapping for critical events
EMOJI_MAP = {
    "server_started": "✓",
    "server_ready": "✓",
    "account_connected": "✓",
    "server_startup_failed": "✗",
    "connection_failed": "✗",
    "auth_warning": "⚠",
    "auth_disabled": "⚠",
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


class ConsoleRenderer:
    """Console renderer with rich integration for colored, human-readable output.

    Formats log entries as: [LEVEL] HH:MM:SS message key=value key=value

    Color scheme:
    - INFO: Green
    - WARNING: Yellow
    - ERROR/CRITICAL: Red
    - DEBUG: Blue

    Minimal emoji support for specific lifecycle events (✓, ✗, ⚠).
    """

    def __init__(self) -> None:
        """Initialize console renderer with rich Console."""
        self.console = Console(file=sys.stderr, force_terminal=True)

        # Color mapping for log levels
        self.level_colors = {
            "debug": "blue",
            "info": "green",
            "warning": "yellow",
            "error": "red",
            "critical": "red bold",
        }

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> str:
        """Render event dictionary as colored console output.

        Args:
            logger: The wrapped logger instance
            method_name: The name of the method called (e.g., "info", "error")
            event_dict: The event dictionary to render

        Returns:
            Formatted log string (rich will handle the actual colorization)
        """
        # Extract core fields
        timestamp = event_dict.pop("timestamp", "")
        level = event_dict.pop("level", "info").lower()
        event = event_dict.pop("event", "")

        # Format timestamp (extract time portion from ISO format)
        if timestamp and "T" in timestamp:
            # ISO format: 2025-11-28T10:30:45.123456Z
            time_part = timestamp.split("T")[1].split(".")[0]  # HH:MM:SS
        else:
            time_part = timestamp

        # Get color for level
        color = self.level_colors.get(level, "white")

        # Format level (uppercase, padded to 5 chars for alignment)
        level_str = f"[{level.upper():5s}]"

        # Add emoji if this is a special event
        emoji = ""
        if event in EMOJI_MAP:
            emoji = f" {EMOJI_MAP[event]}"

        # Build key=value pairs for remaining context
        context_parts = []
        for key, value in event_dict.items():
            # Skip internal structlog fields
            if key.startswith("_"):
                continue

            # Format value appropriately
            if isinstance(value, str):
                # Quote strings with spaces or special chars
                if " " in value or "=" in value:
                    formatted_value = f'"{value}"'
                else:
                    formatted_value = value
            else:
                formatted_value = str(value)

            context_parts.append(f"{key}={formatted_value}")

        context_str = " ".join(context_parts)

        # Build final message
        if context_str:
            message = f"{level_str} {time_part} {event}{emoji} {context_str}"
        else:
            message = f"{level_str} {time_part} {event}{emoji}"

        # Output with color (rich.console handles ANSI codes)
        self.console.print(message, style=color, highlight=False)

        # Return empty string since we've already printed
        return ""


def _create_console_renderer() -> ConsoleRenderer:
    """Create console renderer instance.

    Returns:
        Configured ConsoleRenderer instance
    """
    return ConsoleRenderer()


def configure_logging(json_format: bool = False, log_level: str = "INFO") -> None:
    """Configure structlog with single pipeline and dual renderers.

    This function sets up structured logging with a shared processor chain
    and either console (default) or JSON renderer for output.

    Args:
        json_format: If True, use JSON renderer for production. If False, use console renderer.
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
        structlog.contextvars.merge_contextvars,  # Include bound context
        structlog.stdlib.add_log_level,  # Add log level to event dict
        structlog.stdlib.add_logger_name,  # Add logger name to event dict
        structlog.processors.TimeStamper(fmt="iso", utc=True),  # ISO 8601 timestamps
        structlog.processors.StackInfoRenderer(),  # Render stack traces
        structlog.processors.format_exc_info,  # Format exceptions
        structlog.processors.UnicodeDecoder(),  # Decode unicode strings
        _filter_sensitive_data,  # Redact sensitive fields
    ]

    # Choose renderer based on configuration
    if json_format:
        # Production: JSON Lines format
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: Rich-enhanced console output
        renderer = _create_console_renderer()

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [renderer],
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
