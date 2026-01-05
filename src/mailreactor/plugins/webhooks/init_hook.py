"""Webhook configuration hook for init wizard.

This module implements the webhook init hook that prompts users for webhook
URL configuration during mailreactor init. The hook:
- Adds --no-webhook-validation CLI flag to init command
- Prompts for message_received URL (optional)
- Tests webhook connectivity with HTTP POST
- Exits on test failure (unless --no-webhook-validation)
- Always adds webhooks section to config (even if empty)

The hook auto-registers on import.

Story 3-29-5: Plugin Init Hook System (AC-3)
"""

import asyncio
from typing import Any, Callable

import httpx
import structlog
import typer
from rich.console import Console

from mailreactor.core.plugin_decorator import add_cli_option
from mailreactor.core.plugin_hooks import register_init_hook

logger = structlog.get_logger()


class WebhookInitHook:
    """Init hook for webhook configuration.

    Prompts user for webhook URL and tests connectivity during init wizard.
    Returns webhooks config section for mailreactor.yaml.
    """

    def add_cli_options(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Add --no-webhook-validation flag to init command.

        Args:
            func: The init_wizard function to decorate

        Returns:
            Decorated function with --no-webhook-validation option
        """
        return add_cli_option(
            "no_webhook_validation",
            "--no-webhook-validation",
            "Skip webhook connectivity test",
            bool,
            False,
        )(func)

    def prompt_config(self, console: Console, **kwargs: Any) -> dict[str, Any]:
        """Prompt for webhook configuration with connectivity testing.

        Args:
            console: Rich console for formatted output
            **kwargs: CLI options (no_webhook_validation, etc.)

        Returns:
            Config dict: {"webhooks": {"message_received": url or None}}
            Always returns webhooks section (even if empty)

        Flow:
            1. Prompt for URL (optional - can be empty)
            2. If URL provided and not --no-webhook-validation: test connectivity
            3. If test fails: exit with error (like IMAP/SMTP)
            4. Return config dict (always includes webhooks section)
        """
        no_validation = kwargs.get("no_webhook_validation", False)

        try:
            # Prompt for URL (optional - empty input is allowed)
            url = typer.prompt(
                "Webhook URL for new emails (optional)", default="", show_default=False
            )

            # If no URL provided, save empty webhook section
            if not url:
                return {"webhooks": {"message_received": None}}

            # Test webhook connectivity (unless skipped)
            if not no_validation:
                with console.status("Testing webhook connection..."):
                    success, error = asyncio.run(_test_webhook(url))

                if success:
                    console.print("✓ Webhook connection successful")
                    typer.echo()
                else:
                    # Exit on failure (like IMAP/SMTP)
                    console.print(f"Could not connect to {url} ({error})")
                    typer.echo()
                    typer.echo("To skip webhook validation, use:")
                    typer.echo("  mailreactor init --no-webhook-validation")
                    raise typer.Exit(1)

            return {"webhooks": {"message_received": url}}

        except (KeyboardInterrupt, EOFError):
            # User cancelled - still save empty webhook section
            console.print("\nWebhook configuration skipped")
            return {"webhooks": {"message_received": None}}
        except typer.Exit:
            # Re-raise exit (don't catch it)
            raise
        except Exception as e:
            # Unexpected error - log and exit
            logger.error("webhook_hook_error", error=str(e), error_type=type(e).__name__)
            console.print(f"⚠ Error configuring webhooks: {e}")
            raise typer.Exit(1)


async def _test_webhook(url: str) -> tuple[bool, str | None]:
    """Test webhook endpoint reachability without sending real data.

    Args:
        url: Webhook URL to test

    Returns:
        Tuple of (success: bool, error_message: str | None)
        - (True, None) on successful connection
        - (False, error_message) on failure

    Implementation:
        - Uses HEAD request (lightweight, no body)
        - Falls back to GET if HEAD not supported
        - Only tests connectivity, doesn't send webhook data
        - Accepts any 2xx/3xx/405 response (405 = Method Not Allowed is OK)
        - 5-second timeout to avoid long waits

    Rationale:
        - HEAD/GET doesn't trigger downstream actions (unlike POST)
        - Doesn't send fake data that might fail schema validation
        - 405 (Method Not Allowed) is acceptable - means endpoint exists
        - This is a connectivity test, not a functional test
    """
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            # Try HEAD first (no body, just checks if endpoint exists)
            try:
                response = await client.head(url)
            except httpx.HTTPStatusError:
                # If HEAD fails, try GET as fallback (some servers don't support HEAD)
                response = await client.get(url)

            # Success conditions:
            # - 2xx: Success
            # - 3xx: Redirect (followed automatically by follow_redirects=True)
            # - 405: Method Not Allowed (endpoint exists, just doesn't accept HEAD/GET)
            # This is fine - we only need to know the endpoint is reachable
            if response.status_code in (405,) or 200 <= response.status_code < 400:
                logger.info(
                    "webhook_test_success",
                    url=url,
                    status_code=response.status_code,
                    method="HEAD" if response.request.method == "HEAD" else "GET",
                )
                return True, None
            else:
                # Non-success response (4xx other than 405, or 5xx)
                error_msg = f"HTTP {response.status_code}"
                logger.warning(
                    "webhook_test_non_success", url=url, status_code=response.status_code
                )
                return False, error_msg

    except httpx.TimeoutException:
        logger.warning("webhook_test_timeout", url=url)
        return False, "Connection timeout"
    except httpx.ConnectError as e:
        logger.warning("webhook_test_connection_error", url=url, error=str(e))
        return False, "Connection refused"
    except Exception as e:
        logger.error(
            "webhook_test_unexpected_error", url=url, error=str(e), error_type=type(e).__name__
        )
        return False, f"{type(e).__name__}: {e}"


# Auto-register hook on import
webhook_hook = WebhookInitHook()
register_init_hook(webhook_hook)
