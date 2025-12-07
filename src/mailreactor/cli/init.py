"""CLI wizard for mailreactor init command.

This module provides an interactive wizard for setting up Mail Reactor with an email account.
The wizard guides users through:
- Email address and password input
- Auto-detection of IMAP/SMTP settings (local → Mozilla → ISP → manual)
- Connection validation with real-time feedback
- YAML configuration file creation with placeholder passwords (Story 2.4 MVP)

Usage:
    mailreactor init
    mailreactor init --no-autoconfig  # Skip auto-detection
    mailreactor init --no-validation  # Skip connection validation (offline mode)
    mailreactor init --verbose        # Show debug logs

Story 2.4 creates plaintext config (placeholder passwords).
Story 2.4 course correction adds flags and unified wizard flow.
Story 2.5 will add master password encryption.
"""

import asyncio
import getpass
import logging
import socket
import ssl as ssl_module
from pathlib import Path
from typing import Any, Coroutine, Optional, Tuple, TypeVar

import aiosmtplib
import structlog
import typer
import yaml
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError
from pydantic import EmailStr, TypeAdapter, ValidationError
from rich.console import Console

from mailreactor.core.provider_detector import detect_provider, get_provider_hint
from mailreactor.models.account import IMAPConfig, ProviderConfig, SMTPConfig

console = Console()
logger = structlog.get_logger()

# Type variable for async function return type
T = TypeVar("T")


def init_wizard(
    no_autoconfig: bool = typer.Option(
        False, "--no-autoconfig", help="Skip auto-detection, manual config only"
    ),
    no_validation: bool = typer.Option(
        False, "--no-validation", help="Skip connection validation (offline mode)"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show debug logs (structlog output)"),
) -> None:
    """Interactive wizard for email account setup.

    Creates mailreactor.yaml in current directory with account credentials.

    Args:
        no_autoconfig: Skip auto-detection, go directly to manual prompts
        no_validation: Skip IMAP/SMTP connection validation (offline mode)
        verbose: Show structlog DEBUG logs (default: ERROR level only)

    Flow (Story 2.4 course correction):
    1. Check for existing config file (exit if found)
    2. Configure structlog based on verbose flag
    3. Prompt for email address (validate with Pydantic EmailStr)
    4. Prompt for password (hidden input via getpass)
    5. Auto-detect provider settings if not --no-autoconfig
    6. Show prompts with detected values as defaults (unified flow)
    7. Show IMAP config summary and validate if not --no-validation
    8. Show SMTP config summary and validate if not --no-validation
    9. Create mailreactor.yaml with placeholder passwords
    10. Set file permissions to 0600
    11. Display success message with next steps

    Story 2.5 will add:
    - Master password prompts
    - Password encryption (PBKDF2 + Fernet)
    - !encrypted YAML tag
    """
    # Configure structlog for wizard (AC-7)
    # In normal mode: CRITICAL level (suppresses DEBUG/INFO/WARNING/ERROR)
    # In verbose mode: DEBUG level (shows all logs)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True),  # No timestamp processor
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if verbose else logging.CRITICAL
        ),
    )

    # Check for existing config file (fail fast)
    config_path = Path("mailreactor.yaml")
    if config_path.exists():
        typer.echo("mailreactor.yaml already exists")
        raise typer.Exit(1)

    # Display wizard header (always the same, no mode indicators per HC correction)
    typer.echo("Mail Reactor Setup Wizard")
    typer.echo()

    # Prompt for email address with validation
    try:
        email_input = typer.prompt("Email")
        # Validate email format with Pydantic EmailStr using TypeAdapter
        email = TypeAdapter(EmailStr).validate_python(email_input)
    except (ValidationError, ValueError):
        # Both Pydantic ValidationError and ValueError can be raised
        typer.echo("Invalid email format")
        raise typer.Exit(1)
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C handling
        typer.echo("\nConfiguration cancelled")
        raise typer.Exit(1)

    # Show proactive App Password hint for major providers (Story 2.4.1)
    domain = email.split("@")[1].lower()
    hint = get_provider_hint(domain)
    if hint:
        typer.echo()
        typer.echo(f"💡 {hint}")
        typer.echo()

    # Prompt for password (hidden input)
    try:
        password = getpass.getpass("Password: ")
        # Accept any password (including blank) per AC
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C handling
        typer.echo("\nConfiguration cancelled")
        raise typer.Exit(1)

    typer.echo()

    # Auto-detect provider settings with spinner (AC-2: skip if --no-autoconfig)
    provider_config: Optional[ProviderConfig] = None
    if not no_autoconfig:
        try:
            with console.status("⠋ Detecting mail server settings..."):
                provider_config = _run_async(detect_provider(email))
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nConfiguration cancelled")
            raise typer.Exit(1)

        # Display detection result
        if provider_config:
            console.print(f"Found settings for {provider_config.provider_name} ✓")
            typer.echo()
        else:
            console.print("Unable to detect mail server settings")
            typer.echo()

    # Unified wizard flow (AC-5): Always prompt, use detected values as defaults
    try:
        # Store initial password for defaults (AC-6)
        initial_password = password

        # IMAP configuration prompts with editable defaults
        imap_config = _prompt_imap_config_unified(email, initial_password, provider_config)

        # IMAP validation with config summary (AC-4)
        if not no_validation:
            # Show IMAP config summary before validation
            typer.echo()
            typer.echo("IMAP Configuration:")
            typer.echo(f"  Host: {imap_config.host}")
            typer.echo(f"  Port: {imap_config.port}")
            typer.echo(f"  SSL: {imap_config.ssl}")
            typer.echo(f"  Username: {imap_config.username}")
            typer.echo()

            # Validate IMAP immediately (early exit on failure per AC-4)
            with console.status("⠋ Testing IMAP connection..."):
                imap_success, imap_error = _run_async(_validate_imap_connection(imap_config))

            if imap_success:
                console.print("✓ IMAP connection successful")
                typer.echo()
            else:
                console.print(imap_error)
                raise typer.Exit(1)

        # SMTP configuration prompts with editable defaults (only after IMAP succeeds)
        smtp_config = _prompt_smtp_config_unified(
            email,
            imap_config.password,
            provider_config,  # SMTP password defaults to IMAP password (AC-6)
        )

        # SMTP validation with config summary (AC-4)
        if not no_validation:
            # Show SMTP config summary before validation
            typer.echo()
            typer.echo("SMTP Configuration:")
            typer.echo(f"  Host: {smtp_config.host}")
            typer.echo(f"  Port: {smtp_config.port}")
            typer.echo(f"  STARTTLS: {smtp_config.starttls}")
            typer.echo(f"  Username: {smtp_config.username}")
            typer.echo()

            # Validate SMTP
            with console.status("⠋ Testing SMTP connection..."):
                smtp_success, smtp_error = _run_async(_validate_smtp_connection(smtp_config))

            if smtp_success:
                console.print("✓ SMTP connection successful")
                typer.echo()
            else:
                console.print(smtp_error)
                raise typer.Exit(1)

    except (KeyboardInterrupt, EOFError):
        typer.echo("\nConfiguration cancelled")
        raise typer.Exit(1)

    # Create mailreactor.yaml with placeholder passwords (Story 2.4 MVP)
    yaml_data = {
        "email": email,
        "imap": {
            "host": imap_config.host,
            "port": imap_config.port,
            "ssl": imap_config.ssl,
            "username": imap_config.username,
            "password": "PLACEHOLDER_PASSWORD",  # pragma: allowlist secret  # Story 2.5 will add encryption
        },
        "smtp": {
            "host": smtp_config.host,
            "port": smtp_config.port,
            "starttls": smtp_config.starttls,
            "username": smtp_config.username,
            "password": "PLACEHOLDER_PASSWORD",  # pragma: allowlist secret  # Story 2.5 will add encryption
        },
    }

    try:
        # Write YAML to file
        with config_path.open("w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        # Set file permissions to 0600 (user read/write only)
        try:
            config_path.chmod(0o600)
        except (OSError, NotImplementedError) as e:
            # Windows may not support POSIX permissions
            logger.warning("file_permissions_not_set", reason="platform_unsupported", error=str(e))

        # Success message (always the same, no validation note per HC correction)
        console.print("Configuration saved to mailreactor.yaml")
        typer.echo()
        typer.echo("To start the server:")
        typer.echo("  mailreactor start")

    except Exception as e:
        typer.echo(f"\n❌ Failed to save configuration: {e}", err=True)
        raise typer.Exit(1)


def _prompt_imap_config_unified(
    email: str, default_password: str, provider_config: Optional[ProviderConfig]
) -> IMAPConfig:
    """Prompt for IMAP configuration with auto-detected defaults (unified flow - AC-5).

    Args:
        email: Email address (used as default username)
        default_password: Password from initial prompt (used as IMAP password default)
        provider_config: Auto-detected provider settings (None if detection failed/skipped)

    Returns:
        IMAPConfig with user-provided or defaulted settings
    """
    # Extract defaults from provider config or use standard defaults
    default_host = provider_config.imap_host if provider_config else ""
    default_port = provider_config.imap_port if provider_config else 993
    default_ssl = provider_config.imap_ssl if provider_config else True

    # Always prompt with defaults (unified code path)
    imap_host = typer.prompt("IMAP server", default=default_host if default_host else None)
    imap_port = typer.prompt("IMAP port", default=default_port, type=int)

    # Y/n prompt for SSL with default
    ssl_default_str = "Y" if default_ssl else "n"
    imap_ssl_input = typer.prompt("IMAP SSL", default=ssl_default_str, show_default=True)
    imap_ssl = imap_ssl_input.lower() in ["y", "yes"]

    imap_username = typer.prompt("IMAP username", default=email)

    # Password prompt with REDACTED hint (AC-6 - HC correction)
    # User cannot see password, but Enter uses default_password value
    imap_password_input = getpass.getpass("IMAP password [REDACTED]: ")
    imap_password = imap_password_input if imap_password_input else default_password

    return IMAPConfig(
        host=imap_host,
        port=imap_port,
        ssl=imap_ssl,
        username=imap_username,
        password=imap_password,
    )


def _prompt_smtp_config_unified(
    email: str, default_password: str, provider_config: Optional[ProviderConfig]
) -> SMTPConfig:
    """Prompt for SMTP configuration with auto-detected defaults (unified flow - AC-5).

    Args:
        email: Email address (used as default username)
        default_password: IMAP password (used as SMTP password default per AC-6)
        provider_config: Auto-detected provider settings (None if detection failed/skipped)

    Returns:
        SMTPConfig with user-provided or defaulted settings
    """
    # Extract defaults from provider config or use standard defaults
    default_host = provider_config.smtp_host if provider_config else ""
    default_port = provider_config.smtp_port if provider_config else 587
    default_starttls = provider_config.smtp_starttls if provider_config else True

    # Always prompt with defaults (unified code path)
    smtp_host = typer.prompt("SMTP server", default=default_host if default_host else None)
    smtp_port = typer.prompt("SMTP port", default=default_port, type=int)

    # Y/n prompt for STARTTLS with default
    starttls_default_str = "Y" if default_starttls else "n"
    smtp_starttls_input = typer.prompt(
        "SMTP STARTTLS", default=starttls_default_str, show_default=True
    )
    smtp_starttls = smtp_starttls_input.lower() in ["y", "yes"]

    smtp_username = typer.prompt("SMTP username", default=email)

    # Password prompt with REDACTED hint (AC-6 - HC correction)
    # Default is IMAP password (password cascade: initial → IMAP → SMTP)
    smtp_password_input = getpass.getpass("SMTP password [REDACTED]: ")
    smtp_password = smtp_password_input if smtp_password_input else default_password

    return SMTPConfig(
        host=smtp_host,
        port=smtp_port,
        starttls=smtp_starttls,
        username=smtp_username,
        password=smtp_password,
    )


def _prompt_imap_config(email: str, default_password: str) -> IMAPConfig:
    """[DEPRECATED] Prompt for IMAP configuration when auto-detection fails.

    This function is preserved for backward compatibility but is no longer used.
    Use _prompt_imap_config_unified() instead (Story 2.4 course correction).

    Args:
        email: Email address (used as default username)
        default_password: Password from initial prompt (used as default)

    Returns:
        IMAPConfig with user-provided settings
    """
    imap_host = typer.prompt("IMAP server")
    imap_port = typer.prompt("IMAP port", default=993, type=int)

    # Y/n prompt for SSL (default Y)
    imap_ssl_input = typer.prompt("IMAP SSL [Y/n]", default="Y", show_default=False)
    imap_ssl = imap_ssl_input.lower() in ["y", "yes", ""]

    imap_username = typer.prompt("IMAP username", default=email)
    imap_password = getpass.getpass("IMAP password: ")

    return IMAPConfig(
        host=imap_host,
        port=imap_port,
        ssl=imap_ssl,
        username=imap_username,
        password=imap_password,
    )


def _prompt_smtp_config(email: str, default_password: str) -> SMTPConfig:
    """[DEPRECATED] Prompt for SMTP configuration after IMAP validation.

    This function is preserved for backward compatibility but is no longer used.
    Use _prompt_smtp_config_unified() instead (Story 2.4 course correction).

    Args:
        email: Email address (used as default username)
        default_password: Password from initial prompt (used as default)

    Returns:
        SMTPConfig with user-provided settings
    """
    smtp_host = typer.prompt("SMTP server")
    smtp_port = typer.prompt("SMTP port", default=587, type=int)

    # Y/n prompt for STARTTLS (default Y)
    smtp_starttls_input = typer.prompt("SMTP STARTTLS [Y/n]", default="Y", show_default=False)
    smtp_starttls = smtp_starttls_input.lower() in ["y", "yes", ""]

    smtp_username = typer.prompt("SMTP username", default=email)
    smtp_password = getpass.getpass("SMTP password: ")

    return SMTPConfig(
        host=smtp_host,
        port=smtp_port,
        starttls=smtp_starttls,
        username=smtp_username,
        password=smtp_password,
    )


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async function in event loop (helper for Typer commands).

    Args:
        coro: Coroutine to execute

    Returns:
        Result of coroutine execution
    """
    return asyncio.run(coro)


async def _validate_imap_connection(imap_config: IMAPConfig) -> Tuple[bool, Optional[str]]:
    """Test IMAP connection using existing IMAPClient (inline implementation).

    Args:
        imap_config: IMAP configuration with credentials

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) on success
        - (False, error_message) on failure
    """

    def _sync_validate() -> Tuple[bool, Optional[str]]:
        """Synchronous IMAP validation (runs in executor)."""
        try:
            logger.info(
                "imap_validation_starting",
                host=imap_config.host,
                port=imap_config.port,
                ssl=imap_config.ssl,
                username=imap_config.username,
            )

            # Connect with 10s timeout
            client = IMAPClient(
                imap_config.host,
                port=imap_config.port,
                ssl=imap_config.ssl,
                timeout=10,
            )
            logger.debug("imap_connected")

            # Attempt login
            client.login(imap_config.username, imap_config.password)
            logger.info("imap_login_success")

            # Logout cleanly
            client.logout()
            logger.debug("imap_logout_complete")
            return True, None

        except socket.timeout as e:
            logger.error("imap_timeout", error=str(e))
            return False, f"Could not connect to {imap_config.host}:{imap_config.port} (timeout)"
        except ConnectionRefusedError as e:
            logger.error("imap_connection_refused", error=str(e))
            return (
                False,
                f"Could not connect to {imap_config.host}:{imap_config.port} (connection refused)",
            )
        except ssl_module.SSLError as e:
            logger.error("imap_ssl_error", error=str(e), error_type=type(e).__name__)
            return False, f"Could not connect to {imap_config.host}:{imap_config.port} (SSL error)"
        except IMAPClientError as e:
            # Check if authentication error
            error_str = str(e).lower()
            if "auth" in error_str or "login" in error_str:
                logger.error("imap_auth_error", error=str(e))
                return False, f"IMAP authentication failed for {imap_config.username}"
            logger.error("imap_client_error", error=str(e))
            return False, f"Could not connect to {imap_config.host}:{imap_config.port}"
        except Exception as e:
            logger.error("imap_generic_error", error=str(e), error_type=type(e).__name__)
            return (
                False,
                f"Could not connect to {imap_config.host}:{imap_config.port}: {type(e).__name__}: {e}",
            )

    # Run sync IMAPClient in executor (non-blocking)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_validate)


async def _validate_smtp_connection(smtp_config: SMTPConfig) -> Tuple[bool, Optional[str]]:
    """Test SMTP connection using existing aiosmtplib (inline implementation).

    Args:
        smtp_config: SMTP configuration with credentials

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) on success
        - (False, error_message) on failure
    """
    smtp = None
    try:
        logger.info(
            "smtp_validation_starting",
            host=smtp_config.host,
            port=smtp_config.port,
            starttls=smtp_config.starttls,
            username=smtp_config.username,
        )

        # Create SMTP client with 10s timeout
        # For STARTTLS (port 587): start with plaintext, use_tls=False
        # For implicit SSL (port 465): start with TLS, use_tls=True
        use_tls = not smtp_config.starttls  # Implicit TLS if not using STARTTLS

        smtp = aiosmtplib.SMTP(
            hostname=smtp_config.host,
            port=smtp_config.port,
            timeout=10,
            use_tls=use_tls,  # False for STARTTLS, True for implicit TLS
        )
        logger.debug("smtp_connecting", use_tls=use_tls)
        await smtp.connect()
        logger.debug(
            "smtp_connected",
            is_tls=smtp.is_connected and hasattr(smtp, "transport") and smtp.transport is not None,
        )

        # Upgrade to STARTTLS if configured
        if smtp_config.starttls:
            # Check if connection is already using TLS (some servers auto-upgrade)
            if (
                hasattr(smtp, "protocol")
                and smtp.protocol is not None
                and hasattr(smtp.protocol, "_stream_writer")
            ):
                stream_writer = smtp.protocol._stream_writer
                transport = stream_writer.transport if stream_writer else None
                already_tls = (
                    transport
                    and hasattr(transport, "get_extra_info")
                    and transport.get_extra_info("sslcontext") is not None
                )
                logger.debug("smtp_starttls_check", already_tls=already_tls)

                if not already_tls:
                    logger.debug("smtp_starttls_starting")
                    await smtp.starttls()
                    logger.debug("smtp_starttls_complete")
                else:
                    logger.debug("smtp_starttls_skipped", reason="connection_already_encrypted")
            else:
                # Fallback: try starttls and catch the error
                try:
                    logger.debug("smtp_starttls_starting")
                    await smtp.starttls()
                    logger.debug("smtp_starttls_complete")
                except aiosmtplib.SMTPException as e:
                    if "already using TLS" in str(e):
                        logger.debug("smtp_starttls_skipped", reason="already_encrypted")
                    else:
                        raise

        # Attempt login
        logger.debug("smtp_login_starting")
        await smtp.login(smtp_config.username, smtp_config.password)
        logger.info("smtp_login_success")

        # Success - close cleanly
        await smtp.quit()
        logger.debug("smtp_quit_complete")
        return True, None

    except asyncio.TimeoutError as e:
        logger.error("smtp_timeout", error=str(e))
        return False, f"Could not connect to {smtp_config.host}:{smtp_config.port} (timeout)"
    except ConnectionRefusedError as e:
        logger.error("smtp_connection_refused", error=str(e))
        return (
            False,
            f"Could not connect to {smtp_config.host}:{smtp_config.port} (connection refused)",
        )
    except ssl_module.SSLError as e:
        logger.error("smtp_ssl_error", error=str(e), error_type=type(e).__name__)
        return False, f"Could not connect to {smtp_config.host}:{smtp_config.port} (SSL error)"
    except aiosmtplib.SMTPAuthenticationError as e:
        logger.error("smtp_auth_error", error=str(e))
        return False, f"SMTP authentication failed for {smtp_config.username}"
    except Exception as e:
        logger.error("smtp_generic_error", error=str(e), error_type=type(e).__name__)
        return (
            False,
            f"Could not connect to {smtp_config.host}:{smtp_config.port}: {type(e).__name__}: {e}",
        )
    finally:
        # Ensure connection is closed even on exception
        if smtp is not None and smtp.is_connected:
            try:
                logger.debug("smtp_cleanup_closing")
                smtp.close()  # close() is synchronous in aiosmtplib, returns None
                logger.debug("smtp_cleanup_complete")
            except Exception as e:
                logger.warning("smtp_cleanup_error", error=str(e))
