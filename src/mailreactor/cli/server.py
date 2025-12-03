"""CLI commands for starting and managing the Mail Reactor server.

This module provides Typer-based CLI commands:
- start: Launch the Mail Reactor API server with Uvicorn
- dev: Development mode with auto-reload (Story 1.8)

Usage:
    mailreactor start
    mailreactor start --host 0.0.0.0 --port 3000
    mailreactor start --json-logs
    python -m mailreactor start
"""

from typing import Optional

import structlog
import typer
import uvicorn

from mailreactor.config import Settings
from mailreactor.main import create_app
from mailreactor.utils.logging import configure_logging

logger = structlog.get_logger()


def start(
    host: str = typer.Option(
        "127.0.0.1", help="Bind host address (default: localhost for security)"
    ),
    port: int = typer.Option(8000, help="Bind port number", min=1, max=65535),
    log_level: str = typer.Option(
        "INFO", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)", case_sensitive=False
    ),
    json_logs: bool = typer.Option(
        False, "--json-logs", help="Enable JSON logging for production (default: colored console)"
    ),
    account: Optional[str] = typer.Option(
        None, help="Email account to add on startup (not implemented yet - Epic 2)"
    ),
) -> None:
    """Start Mail Reactor API server.

    This command starts the FastAPI server on the specified host and port.
    By default, the server binds to localhost (127.0.0.1) for security.

    Examples:
        # Start with defaults (localhost:8000, console logs)
        mailreactor start

        # Start on custom port with JSON logs
        mailreactor start --port 3000 --json-logs

        # Start on all interfaces (WARNING: network exposure)
        mailreactor start --host 0.0.0.0

        # Debug mode
        mailreactor start --log-level DEBUG
    """
    # Configure logging FIRST (before any other initialization)
    configure_logging(json_format=json_logs, log_level=log_level.upper())

    # Log security warning if binding to all interfaces
    if host == "0.0.0.0":
        logger.warning(
            "network_exposure",
            message="Server binding to 0.0.0.0 exposes API to network. "
            "Ensure authentication is configured (Epic 5).",
        )

    # Warn if --account flag is used (not implemented yet)
    if account:
        logger.warning(
            "feature_not_implemented",
            message=f"--account flag is not implemented yet (Epic 2). "
            f"Account '{account}' will be ignored.",
        )

    # Override settings with CLI arguments
    # Note: We don't use the global settings singleton here to avoid
    # environment variable conflicts. CLI flags take precedence.
    settings = Settings(host=host, port=port, log_level=log_level.upper(), json_logs=json_logs)

    # Log server configuration before starting
    logger.info(
        "server_starting",
        host=host,
        port=port,
        log_level=log_level.upper(),
    )

    # Create FastAPI app
    fastapi_app = create_app()

    # Display helpful startup hints
    api_url = f"http://{host}:{port}"
    logger.info(
        "docs_hint",
        url=f"{api_url}/docs",
        message="API docs will be available at this URL once server starts",
    )
    logger.info(
        "account_setup_hint", message="Add account with: mailreactor start --account you@email.com"
    )

    # Start Uvicorn server (uvicorn will log when server is actually running)
    # Note: Uvicorn handles SIGINT (Ctrl+C) and SIGTERM gracefully by default
    # It will shut down cleanly, finishing in-flight requests
    # Note: reload=False for production start command
    # Use reload=True in dev command (Story 1.8)
    uvicorn.run(
        fastapi_app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),  # Uvicorn expects lowercase ('info', 'debug'), we store uppercase
        access_log=False,  # We use structured logging instead
        log_config=None,  # Don't let Uvicorn reconfigure logging - we already did it
    )
