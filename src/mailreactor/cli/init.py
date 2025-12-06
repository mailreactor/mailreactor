"""CLI wizard for mailreactor init command.

This module provides an interactive wizard for setting up Mail Reactor with an email account.
The wizard guides users through:
- Email address and password input
- Auto-detection of IMAP/SMTP settings (local → Mozilla → ISP → manual)
- Connection validation with real-time feedback
- YAML configuration file creation with placeholder passwords (Story 2.4 MVP)

Usage:
    mailreactor init

Story 2.4 creates plaintext config (placeholder passwords).
Story 2.5 will add master password encryption.
"""

import asyncio
import getpass
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

from mailreactor.core.provider_detector import detect_provider, get_app_password_hint
from mailreactor.models.account import IMAPConfig, SMTPConfig

console = Console()
logger = structlog.get_logger()

# Type variable for async function return type
T = TypeVar("T")


def init_wizard() -> None:
    """Interactive wizard for email account setup.

    Creates mailreactor.yaml in current directory with account credentials.

    Flow (Story 2.4 MVP - plaintext passwords):
    1. Check for existing config file (exit if found)
    2. Prompt for email address (validate with Pydantic EmailStr)
    3. Prompt for password (hidden input via getpass)
    4. Auto-detect provider settings (local → Mozilla → ISP → manual)
    5. Validate IMAP connection (inline implementation)
    6. Validate SMTP connection (inline implementation)
    7. Create mailreactor.yaml with placeholder passwords
    8. Set file permissions to 0600
    9. Display success message with next steps

    Story 2.5 will add:
    - Master password prompts
    - Password encryption (PBKDF2 + Fernet)
    - !encrypted YAML tag
    """
    # Check for existing config file (fail fast)
    config_path = Path("mailreactor.yaml")
    if config_path.exists():
        typer.echo("mailreactor.yaml already exists")
        raise typer.Exit(1)

    # Display wizard header
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

    # Prompt for password (hidden input)
    try:
        password = getpass.getpass("Password: ")
        # Accept any password (including blank) per AC
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C handling
        typer.echo("\nConfiguration cancelled")
        raise typer.Exit(1)

    typer.echo()

    # Auto-detect provider settings with spinner
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

        # Build IMAP/SMTP configs from detected provider
        imap_config = IMAPConfig(
            host=provider_config.imap_host,
            port=provider_config.imap_port,
            ssl=provider_config.imap_ssl,
            username=email,  # Assume username = email (MVP)
            password=password,  # Use same password for IMAP (MVP)
        )
        smtp_config = SMTPConfig(
            host=provider_config.smtp_host,
            port=provider_config.smtp_port,
            starttls=provider_config.smtp_starttls,
            username=email,  # Assume username = email (MVP)
            password=password,  # Use same password for SMTP (MVP)
        )
    else:
        console.print("Unable to detect mail server settings")
        typer.echo()

        # Manual configuration prompts
        try:
            imap_config = _prompt_imap_config(email, password)
            smtp_config = _prompt_smtp_config(email, password)
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nConfiguration cancelled")
            raise typer.Exit(1)

    # Validate IMAP connection with spinner
    try:
        with console.status("⠋ Testing IMAP connection..."):
            imap_success, imap_error = _run_async(_validate_imap_connection(imap_config))

        if imap_success:
            console.print("✓ IMAP connection successful")
        else:
            console.print(imap_error)

            # Show provider-specific hint for auth failures
            if imap_error and "authentication failed" in imap_error.lower():
                domain = email.split("@")[1].lower()
                hint = get_app_password_hint(domain)
                if hint:
                    typer.echo()
                    typer.echo(hint)

            raise typer.Exit(1)
    except (KeyboardInterrupt, EOFError):
        typer.echo("\nConfiguration cancelled")
        raise typer.Exit(1)

    typer.echo()

    # Validate SMTP connection with spinner
    try:
        with console.status("⠋ Testing SMTP connection..."):
            smtp_success, smtp_error = _run_async(_validate_smtp_connection(smtp_config))

        if smtp_success:
            console.print("✓ SMTP connection successful")
        else:
            console.print(smtp_error)

            # Show provider-specific hint for auth failures
            if smtp_error and "authentication failed" in smtp_error.lower():
                domain = email.split("@")[1].lower()
                hint = get_app_password_hint(domain)
                if hint:
                    typer.echo()
                    typer.echo(hint)

            raise typer.Exit(1)
    except (KeyboardInterrupt, EOFError):
        typer.echo("\nConfiguration cancelled")
        raise typer.Exit(1)

    typer.echo()

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

        # Success message
        console.print("Configuration saved to mailreactor.yaml")
        typer.echo()
        typer.echo("To start the server:")
        typer.echo("  mailreactor start")

    except Exception as e:
        typer.echo(f"\n❌ Failed to save configuration: {e}", err=True)
        raise typer.Exit(1)


def _prompt_imap_config(email: str, default_password: str) -> IMAPConfig:
    """Prompt for IMAP configuration when auto-detection fails.

    Args:
        email: Email address (used as default username)
        default_password: Password from initial prompt (used as default)

    Returns:
        IMAPConfig with user-provided settings
    """
    imap_host = typer.prompt("IMAP server")
    imap_port = typer.prompt("IMAP port", default=993, type=int)

    # Y/n prompt for SSL
    imap_ssl_input = typer.prompt("IMAP SSL", default="Y")
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
    """Prompt for SMTP configuration after IMAP validation.

    Args:
        email: Email address (used as default username)
        default_password: Password from initial prompt (used as default)

    Returns:
        SMTPConfig with user-provided settings
    """
    smtp_host = typer.prompt("SMTP server")
    smtp_port = typer.prompt("SMTP port", default=587, type=int)

    # Y/n prompt for STARTTLS
    smtp_starttls_input = typer.prompt("SMTP STARTTLS", default="Y")
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
