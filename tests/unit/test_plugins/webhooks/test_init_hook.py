"""Tests for webhook init hook (Story 3-29-5: AC-3).

Tests webhook configuration hook:
- add_cli_options adds --no-webhook-validation flag
- URL prompt (optional - can be empty)
- HTTP HEAD connectivity test (success)
- HTTP HEAD connectivity test (failure - exits)
- HTTP HEAD fallback to GET
- Skip validation flag
- Empty input saves null webhook
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import typer
from rich.console import Console

from mailreactor.plugins.webhooks.init_hook import WebhookInitHook, _test_webhook


class TestWebhookInitHook:
    """Tests for WebhookInitHook class."""

    def test_add_cli_options_adds_flag(self):
        """Test add_cli_options adds --no-webhook-validation flag."""
        hook = WebhookInitHook()

        # Mock function
        mock_func = MagicMock()

        # Apply decorator
        result = hook.add_cli_options(mock_func)

        # Verify decorator was applied (function is wrapped)
        assert result is not None
        assert result is not mock_func  # Wrapped function is different

    @patch("mailreactor.plugins.webhooks.init_hook.typer.prompt")
    @patch("mailreactor.plugins.webhooks.init_hook.asyncio.run")
    def test_prompt_config_success(self, mock_asyncio_run, mock_prompt):
        """Test webhook hook with successful connectivity test (AC-3)."""
        # Mock user input
        mock_prompt.return_value = "http://localhost:3000/webhook"

        # Mock successful HTTP HEAD request
        mock_asyncio_run.return_value = (True, None)

        # Execute hook
        hook = WebhookInitHook()
        console = Console()
        result = hook.prompt_config(console)

        # Verify result
        assert result == {"webhooks": {"message_received": "http://localhost:3000/webhook"}}

        # Verify prompt called
        mock_prompt.assert_called_once()

        # Verify connectivity test called
        mock_asyncio_run.assert_called_once()

    @patch("mailreactor.plugins.webhooks.init_hook.typer.prompt")
    @patch("mailreactor.plugins.webhooks.init_hook.asyncio.run")
    def test_prompt_config_http_failure_exits(self, mock_asyncio_run, mock_prompt):
        """Test webhook hook with failed connectivity test (AC-3 - exits like IMAP/SMTP)."""
        # Mock user input
        mock_prompt.return_value = "http://localhost:3000/webhook"

        # Mock failed HTTP HEAD request
        mock_asyncio_run.return_value = (False, "Connection refused")

        # Execute hook - should raise Exit
        hook = WebhookInitHook()
        console = Console()

        with pytest.raises(typer.Exit) as exc_info:
            hook.prompt_config(console)

        # Verify exit code is 1
        assert exc_info.value.exit_code == 1

    @patch("mailreactor.plugins.webhooks.init_hook.typer.prompt")
    @patch("mailreactor.plugins.webhooks.init_hook.asyncio.run")
    def test_prompt_config_skip_validation(self, mock_asyncio_run, mock_prompt):
        """Test webhook hook with --no-webhook-validation flag."""
        # Mock user input
        mock_prompt.return_value = "http://localhost:3000/webhook"

        # Execute hook with no_webhook_validation=True
        hook = WebhookInitHook()
        console = Console()
        result = hook.prompt_config(console, no_webhook_validation=True)

        # Verify result (URL saved)
        assert result == {"webhooks": {"message_received": "http://localhost:3000/webhook"}}

        # Verify connectivity test NOT called
        mock_asyncio_run.assert_not_called()

    @patch("mailreactor.plugins.webhooks.init_hook.typer.prompt")
    def test_prompt_config_empty_input(self, mock_prompt):
        """Test webhook hook with empty input (optional URL)."""
        # Mock empty input
        mock_prompt.return_value = ""

        # Execute hook
        hook = WebhookInitHook()
        console = Console()
        result = hook.prompt_config(console)

        # Verify empty webhook section with null value
        assert result == {"webhooks": {"message_received": None}}

    @patch("mailreactor.plugins.webhooks.init_hook.typer.prompt")
    def test_prompt_config_keyboard_interrupt(self, mock_prompt):
        """Test webhook hook with user cancellation."""
        # Mock user cancellation
        mock_prompt.side_effect = KeyboardInterrupt

        # Execute hook
        hook = WebhookInitHook()
        console = Console()
        result = hook.prompt_config(console)

        # Verify empty webhook section with null value
        assert result == {"webhooks": {"message_received": None}}


class TestWebhookConnectivityTest:
    """Tests for _test_webhook function."""

    @pytest.mark.asyncio
    async def test_webhook_test_success_head_200(self):
        """Test webhook connectivity with HEAD 200 OK response."""
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.request.method = "HEAD"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "mailreactor.plugins.webhooks.init_hook.httpx.AsyncClient", return_value=mock_client
        ):
            success, error = await _test_webhook("http://localhost:3000/webhook")

        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_webhook_test_success_405_method_not_allowed(self):
        """Test webhook connectivity accepts 405 (endpoint exists, method not supported)."""
        # Mock httpx.AsyncClient with 405 response (Method Not Allowed is OK - means endpoint exists)
        mock_response = MagicMock()
        mock_response.status_code = 405
        mock_response.request.method = "HEAD"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "mailreactor.plugins.webhooks.init_hook.httpx.AsyncClient", return_value=mock_client
        ):
            success, error = await _test_webhook("http://localhost:3000/webhook")

        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_webhook_test_fallback_to_get(self):
        """Test webhook connectivity falls back to GET if HEAD fails."""
        # Mock HEAD failing with HTTPStatusError, then GET succeeds
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.request.method = "GET"

        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=MagicMock()
        )
        mock_client.get.return_value = mock_get_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "mailreactor.plugins.webhooks.init_hook.httpx.AsyncClient", return_value=mock_client
        ):
            success, error = await _test_webhook("http://localhost:3000/webhook")

        assert success is True
        assert error is None
        # Verify GET was called as fallback
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_test_404_not_found(self):
        """Test webhook connectivity with 404 response (endpoint doesn't exist)."""
        # Mock httpx.AsyncClient with 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.request.method = "HEAD"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "mailreactor.plugins.webhooks.init_hook.httpx.AsyncClient", return_value=mock_client
        ):
            success, error = await _test_webhook("http://localhost:3000/webhook")

        assert success is False
        assert error == "HTTP 404"

    @pytest.mark.asyncio
    async def test_webhook_test_timeout(self):
        """Test webhook connectivity with timeout."""
        # Mock httpx.AsyncClient with timeout
        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.TimeoutException("Timeout")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "mailreactor.plugins.webhooks.init_hook.httpx.AsyncClient", return_value=mock_client
        ):
            success, error = await _test_webhook("http://localhost:3000/webhook")

        assert success is False
        assert error == "Connection timeout"

    @pytest.mark.asyncio
    async def test_webhook_test_connection_error(self):
        """Test webhook connectivity with connection refused."""
        # Mock httpx.AsyncClient with connection error
        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "mailreactor.plugins.webhooks.init_hook.httpx.AsyncClient", return_value=mock_client
        ):
            success, error = await _test_webhook("http://localhost:3000/webhook")

        assert success is False
        assert error == "Connection refused"
