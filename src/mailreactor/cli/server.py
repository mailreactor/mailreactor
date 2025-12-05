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
from mailreactor.utils.logging import configure_logging
from mailreactor.utils.version import get_app_version

logger = structlog.get_logger()


def _run_server(
    host: str,
    port: int,
    log_level: str,
    json_logs: bool,
    dev_mode: bool = False,
    account: Optional[str] = None,
) -> None:
    """Shared server startup logic for start and dev commands.

    Args:
        host: Bind host address
        port: Bind port number
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Enable JSON logging format
        dev_mode: Enable development mode with auto-reload (default: False)
        account: Email account to add on startup (not implemented - Epic 2)
    """
    # Configure logging FIRST (before any other initialization)
    configure_logging(json_format=json_logs, log_level=log_level.upper())

    # Log development mode warning if in dev mode
    if dev_mode:
        logger.warning(
            "development_mode",
            production_mode="run: mailreactor start",
        )
        logger.info(
            "development_mode",
            auto_reload=True,
            watch_dir="src/mailreactor",
        )

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
    settings = Settings(host=host, port=port, log_level=log_level.upper(), json_logs=json_logs)

    # Log server configuration
    logger.info(
        "server_starting",
        host=host,
        port=port,
        log_level=log_level.upper(),
        version=get_app_version(),
    )

    # Display helpful startup tips
    api_url = f"http://{host}:{port}"
    logger.info(
        "usage_tip",
        docs_url=f"{api_url}/docs",
        redoc_url=f"{api_url}/redoc",
    )

    # Show account command tip with appropriate command name
    command_name = "dev" if dev_mode else "start"
    logger.info(
        "usage_tip",
        account_command=f"mailreactor {command_name} --account you@email.com",
    )

    # Start Uvicorn server (always use factory pattern)
    uvicorn_config = {
        "host": settings.host,
        "port": settings.port,
        "log_level": settings.log_level.lower(),
        "access_log": False,
        "log_config": None,
        "factory": True,
    }

    # Add reload-specific config if in development mode
    if dev_mode:
        uvicorn_config.update(
            {
                "reload": True,
                "reload_dirs": ["src/mailreactor"],
                "reload_delay": 0.5,
            }
        )

    uvicorn.run("mailreactor.main:create_app", **uvicorn_config)


def start(
    host: str = typer.Option(
        "127.0.0.1", help="Bind host address (default: localhost for security)"
    ),
    port: int = typer.Option(8000, help="Bind port number", min=1, max=65535),
    log_level: str = typer.Option(
        "INFO", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)", case_sensitive=False
    ),
    json_logs: bool = typer.Option(
        False, "--json-logs", help="Enable JSON logging (default: colored console)"
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
    _run_server(
        host=host,
        port=port,
        log_level=log_level,
        json_logs=json_logs,
        dev_mode=False,
        account=account,
    )


def dev(
    host: str = typer.Option(
        "127.0.0.1", help="Bind host address (default: localhost for security)"
    ),
    port: int = typer.Option(8000, help="Bind port number", min=1, max=65535),
    log_level: str = typer.Option(
        "DEBUG", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)", case_sensitive=False
    ),
    json_logs: bool = typer.Option(
        False, "--json-logs", help="Enable JSON logging (default: colored console for dev)"
    ),
    account: Optional[str] = typer.Option(
        None, help="Email account to add on startup (not implemented yet - Epic 2)"
    ),
) -> None:
    """Start development server with auto-reload.

    This command starts the FastAPI server in development mode with file watching
    enabled. The server will automatically reload when Python source files change
    in the src/mailreactor/ directory.

    WARNING: This mode is for local development only. Do NOT use in production.

    Examples:
        # Start dev server with defaults
        mailreactor dev

        # Custom port with INFO logging
        mailreactor dev --port 3000 --log-level INFO

        # Enable JSON logs (for testing log output)
        mailreactor dev --json-logs
    """
    _run_server(
        host=host,
        port=port,
        log_level=log_level,
        json_logs=json_logs,
        dev_mode=True,
        account=account,
    )
