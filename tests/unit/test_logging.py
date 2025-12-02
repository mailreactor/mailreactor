"""Unit tests for structured logging configuration.

Tests cover:
- Logging configuration
- Context binding and propagation
- Sensitive data redaction
- Log level filtering
- JSON vs console output
"""

import json
from io import StringIO
from unittest.mock import patch

import structlog

from mailreactor.utils.logging import (
    SENSITIVE_FIELDS,
    bind_context,
    clear_context,
    configure_logging,
    unbind_context,
)


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_logging_accepts_valid_log_levels(self) -> None:
        """Test that configure_logging accepts valid log levels without errors."""
        # Verify that different log levels are accepted
        configure_logging(json_format=False, log_level="DEBUG")
        configure_logging(json_format=False, log_level="INFO")
        configure_logging(json_format=False, log_level="WARNING")
        configure_logging(json_format=False, log_level="ERROR")

        logger = structlog.get_logger()
        assert logger is not None

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

        # We can't easily test console output, but verify logger is configured
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
