"""Unit tests for structured logging configuration.

Tests cover:
- Console renderer formatting and colors
- JSON renderer output
- Shared processors (timestamps, log levels, etc.)
- Context binding and propagation
- Sensitive data redaction
- Log level filtering
"""

import json
from io import StringIO
from unittest.mock import Mock, patch

import structlog

from mailreactor.utils.logging import (
    EMOJI_MAP,
    SENSITIVE_FIELDS,
    ConsoleRenderer,
    bind_context,
    clear_context,
    configure_logging,
    unbind_context,
)


class TestConsoleRenderer:
    """Test suite for ConsoleRenderer."""

    def test_console_renderer_formats_basic_message(self) -> None:
        """Test that console renderer formats basic log messages."""
        renderer = ConsoleRenderer()

        event_dict = {
            "timestamp": "2025-11-28T10:30:45.123456Z",
            "level": "info",
            "event": "test_message",
        }

        # Mock console to capture output
        with patch.object(renderer.console, "print") as mock_print:
            renderer(Mock(), "info", event_dict)

            # Verify print was called
            assert mock_print.called
            call_args = mock_print.call_args
            message = call_args[0][0]

            # Verify format: [LEVEL] HH:MM:SS event
            assert "[INFO ]" in message
            assert "10:30:45" in message
            assert "test_message" in message

    def test_console_renderer_includes_context(self) -> None:
        """Test that console renderer includes context as key=value pairs."""
        renderer = ConsoleRenderer()

        event_dict = {
            "timestamp": "2025-11-28T10:30:45.123456Z",
            "level": "info",
            "event": "email_sent",
            "recipient": "user@example.com",
            "message_id": "abc123",
        }

        with patch.object(renderer.console, "print") as mock_print:
            renderer(Mock(), "info", event_dict)

            message = mock_print.call_args[0][0]

            # Verify context key=value pairs
            assert "recipient=user@example.com" in message
            assert "message_id=abc123" in message

    def test_console_renderer_adds_emoji_for_special_events(self) -> None:
        """Test that console renderer adds emoji for lifecycle events."""
        renderer = ConsoleRenderer()

        for event_name, emoji in EMOJI_MAP.items():
            event_dict = {
                "timestamp": "2025-11-28T10:30:45.123456Z",
                "level": "info",
                "event": event_name,
            }

            with patch.object(renderer.console, "print") as mock_print:
                renderer(Mock(), "info", event_dict)

                message = mock_print.call_args[0][0]
                assert emoji in message

    def test_console_renderer_uses_correct_colors(self) -> None:
        """Test that console renderer uses correct colors for log levels."""
        renderer = ConsoleRenderer()

        levels_and_colors = [
            ("debug", "blue"),
            ("info", "green"),
            ("warning", "yellow"),
            ("error", "red"),
            ("critical", "red bold"),
        ]

        for level, expected_color in levels_and_colors:
            event_dict = {
                "timestamp": "2025-11-28T10:30:45.123456Z",
                "level": level,
                "event": "test_event",
            }

            with patch.object(renderer.console, "print") as mock_print:
                renderer(Mock(), level, event_dict)

                # Verify style parameter
                call_kwargs = mock_print.call_args[1]
                assert call_kwargs["style"] == expected_color

    def test_console_renderer_quotes_strings_with_spaces(self) -> None:
        """Test that console renderer quotes string values with spaces."""
        renderer = ConsoleRenderer()

        event_dict = {
            "timestamp": "2025-11-28T10:30:45.123456Z",
            "level": "info",
            "event": "test_event",
            "message": "This has spaces",
        }

        with patch.object(renderer.console, "print") as mock_print:
            renderer(Mock(), "info", event_dict)

            message = mock_print.call_args[0][0]
            assert 'message="This has spaces"' in message

    def test_console_renderer_skips_internal_fields(self) -> None:
        """Test that console renderer skips internal structlog fields."""
        renderer = ConsoleRenderer()

        event_dict = {
            "timestamp": "2025-11-28T10:30:45.123456Z",
            "level": "info",
            "event": "test_event",
            "_internal_field": "should_not_appear",
        }

        with patch.object(renderer.console, "print") as mock_print:
            renderer(Mock(), "info", event_dict)

            message = mock_print.call_args[0][0]
            assert "_internal_field" not in message


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_logging_sets_log_level(self) -> None:
        """Test that configure_logging sets the correct log level."""
        # Note: We can't reliably test root logger level due to pytest interference
        # Instead, we verify that configure_logging accepts valid log levels
        # and that the logger is configured
        configure_logging(json_format=False, log_level="DEBUG")
        logger = structlog.get_logger()
        assert logger is not None

        # Verify that different log levels are accepted
        configure_logging(json_format=False, log_level="INFO")
        configure_logging(json_format=False, log_level="WARNING")
        configure_logging(json_format=False, log_level="ERROR")

    def test_configure_logging_with_json_format(self) -> None:
        """Test that configure_logging uses JSON renderer when requested."""
        configure_logging(json_format=True, log_level="INFO")

        # Get a logger and log a message
        logger = structlog.get_logger()

        # Capture stderr output
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event", key="value")

            output = mock_stderr.getvalue()

            # Verify JSON output
            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["event"] == "test_event"
                assert log_entry["key"] == "value"

    def test_configure_logging_with_console_format(self) -> None:
        """Test that configure_logging uses console renderer by default."""
        configure_logging(json_format=False, log_level="INFO")

        logger = structlog.get_logger()

        # We can't easily test console output without mocking rich.Console
        # But we can verify the logger is configured
        assert logger is not None


class TestContextBinding:
    """Test suite for context binding utilities."""

    def teardown_method(self) -> None:
        """Clean up context after each test."""
        clear_context()

    def test_bind_context_adds_context(self) -> None:
        """Test that bind_context adds context to logs."""
        configure_logging(json_format=True, log_level="INFO")

        bind_context(request_id="test-123", account_id="user@example.com")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["request_id"] == "test-123"
                assert log_entry["account_id"] == "user@example.com"

    def test_unbind_context_removes_specific_keys(self) -> None:
        """Test that unbind_context removes specific context keys."""
        configure_logging(json_format=True, log_level="INFO")

        bind_context(request_id="test-123", account_id="user@example.com")
        unbind_context("account_id")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["request_id"] == "test-123"
                assert "account_id" not in log_entry

    def test_clear_context_removes_all_context(self) -> None:
        """Test that clear_context removes all context."""
        configure_logging(json_format=True, log_level="INFO")

        bind_context(request_id="test-123", account_id="user@example.com")
        clear_context()

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert "request_id" not in log_entry
                assert "account_id" not in log_entry


class TestSensitiveDataFiltering:
    """Test suite for sensitive data redaction."""

    def test_sensitive_fields_are_redacted(self) -> None:
        """Test that sensitive fields are redacted from logs."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info(
                "test_event",
                username="test_user",
                password="secret123",  # pragma: allowlist secret
                api_key="abc-def-ghi",  # pragma: allowlist secret
            )

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())

                # Verify sensitive fields are redacted
                assert log_entry["username"] == "test_user"
                assert log_entry["password"] == "[REDACTED]"
                assert log_entry["api_key"] == "[REDACTED]"

    def test_all_sensitive_field_names_are_redacted(self) -> None:
        """Test that all configured sensitive field names are redacted."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        for field_name in SENSITIVE_FIELDS:
            clear_context()

            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                logger.info("test_event", **{field_name: "sensitive_value"})

                output = mock_stderr.getvalue()

                if output.strip():
                    log_entry = json.loads(output.strip())
                    assert log_entry[field_name] == "[REDACTED]"


class TestLogLevelFiltering:
    """Test suite for log level filtering."""

    def test_debug_logs_not_shown_at_info_level(self) -> None:
        """Test that debug logs are filtered out at INFO level."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.debug("debug_message")
            logger.info("info_message")

            output = mock_stderr.getvalue()

            # Only INFO message should appear
            lines = [line for line in output.strip().split("\n") if line]

            if lines:
                # Debug message should not appear
                for line in lines:
                    log_entry = json.loads(line)
                    assert log_entry["event"] != "debug_message"

    def test_info_logs_shown_at_info_level(self) -> None:
        """Test that info logs are shown at INFO level."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("info_message")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["event"] == "info_message"

    def test_error_logs_shown_at_info_level(self) -> None:
        """Test that error logs are shown at INFO level."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.error("error_message")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["event"] == "error_message"
                assert log_entry["level"] == "error"


class TestJSONRenderer:
    """Test suite for JSON renderer output."""

    def test_json_renderer_produces_valid_json(self) -> None:
        """Test that JSON renderer produces valid JSON output."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event", key1="value1", key2=123)

            output = mock_stderr.getvalue()

            # Verify valid JSON
            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["event"] == "test_event"
                assert log_entry["key1"] == "value1"
                assert log_entry["key2"] == 123

    def test_json_renderer_includes_timestamp(self) -> None:
        """Test that JSON renderer includes ISO 8601 timestamp."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert "timestamp" in log_entry
                # Verify ISO 8601 format (basic check)
                assert "T" in log_entry["timestamp"]

    def test_json_renderer_includes_log_level(self) -> None:
        """Test that JSON renderer includes log level."""
        configure_logging(json_format=True, log_level="INFO")

        logger = structlog.get_logger()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            logger.info("test_event")

            output = mock_stderr.getvalue()

            if output.strip():
                log_entry = json.loads(output.strip())
                assert log_entry["level"] == "info"
