"""CLI commands for starting and managing the Mail Reactor server.

This module provides Typer-based CLI commands:
- start: Launch the Mail Reactor API server with Uvicorn
- dev: Development mode with auto-reload (Story 1.8)

Usage:
    mailreactor start
    mailreactor start --host 0.0.0.0 --port 3000
    mailreactor start --config /path/to/custom.yaml
    mailreactor start --json-logs
    python -m mailreactor start
"""

import getpass
import os
from pathlib import Path
from typing import Optional

import structlog
import typer
import uvicorn
from cryptography.fernet import InvalidToken

from mailreactor.config import Settings
from mailreactor.core.config import load_config
from mailreactor.models.account import AccountConfig
from mailreactor.utils.logging import configure_logging
from mailreactor.utils.version import get_app_version

logger = structlog.get_logger()


def load_account_config(config_path: Path) -> AccountConfig:
    """Load and decrypt account config from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        AccountConfig with decrypted credentials

    Raises:
        typer.Exit: If config missing or decryption fails (exit code 1)
    """
    # 1. Check file exists FIRST (before asking for password)
    if not config_path.exists():
        logger.error(
            "config_not_found",
            path=str(config_path),
            help="run 'mailreactor init' or 'mailreactor start --config path/to/yaml'",
        )
        raise typer.Exit(1)

    # 2. Get master password BEFORE any other logging (clean UX)
    master_password = os.environ.get("MAILREACTOR_PASSWORD")
    if master_password:
        logger.info("master_password", from_env="MAILREACTOR_PASSWORD")
    else:
        master_password = getpass.getpass("Master password: ")

    # 3. Load config (logs come AFTER password prompt)
    try:
        config_dict = load_config(config_path)
        logger.info("config_loaded", path=str(config_path))
    except Exception as e:
        logger.error("config_parse_error", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(1)

    # 4. Decrypt credentials
    try:
        account_config = AccountConfig.from_yaml(config_dict, master_password)
    except InvalidToken:
        logger.error("decryption_failed", reason="invalid_master_password")
        raise typer.Exit(1)
    except Exception as e:
        logger.error("decryption_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(1)

    # 5. Log successful configuration
    logger.info(
        "account_configured",
        email=account_config.email,
        imap_host=account_config.imap.host,
        smtp_host=account_config.smtp.host,
    )

    return account_config


def _run_server(
    host: str,
    port: int,
    log_level: str,
    json_logs: bool,
    dev_mode: bool = False,
    config_path: Optional[Path] = None,
) -> None:
    """Shared server startup logic for start and dev commands.

    Args:
        host: Bind host address
        port: Bind port number
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Enable JSON logging format
        dev_mode: Enable development mode with auto-reload (default: False)
        config_path: Path to mailreactor.yaml config file (default: ./mailreactor.yaml)
    """
    # Configure logging FIRST (before any other initialization)
    configure_logging(json_format=json_logs, log_level=log_level.upper())

    # Load account configuration from file (Story 2.6)
    if config_path is None:
        config_path = Path("mailreactor.yaml")

    account_config = load_account_config(config_path)  # noqa: F841

    # TODO: Pass account_config to FastAPI app factory (requires main.py update)
    # NOTE: account_config is loaded and validated but not yet passed to main.py
    # This will be implemented in the next story when create_app() is updated
    # to accept AccountConfig parameter

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
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to config file (default: mailreactor.yaml in current directory)",
    ),
) -> None:
    """Start Mail Reactor API server.

    This command starts the FastAPI server on the specified host and port.
    By default, the server binds to localhost (127.0.0.1) for security.

    Configuration is loaded from mailreactor.yaml in the current directory.
    Use 'mailreactor init' to create a config file if it doesn't exist.
    """
    config_path = Path(config) if config else None
    _run_server(
        host=host,
        port=port,
        log_level=log_level,
        json_logs=json_logs,
        dev_mode=False,
        config_path=config_path,
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
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to config file (default: mailreactor.yaml in current directory)",
    ),
) -> None:
    """Start development server with auto-reload.

    This command starts the FastAPI server in development mode with file watching
    enabled. The server will automatically reload when Python source files change.

    Configuration is loaded from mailreactor.yaml in the current directory.
    Use 'mailreactor init' to create a config file if it doesn't exist.
    """
    config_path = Path(config) if config else None
    _run_server(
        host=host,
        port=port,
        log_level=log_level,
        json_logs=json_logs,
        dev_mode=True,
        config_path=config_path,
    )
