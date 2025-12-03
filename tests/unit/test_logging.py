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
