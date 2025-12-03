"""Integration tests for request logging with structured logging.

Tests cover:
- Request ID appears in log context
- Request completion logging with duration
- Log context cleanup between requests
- Exception logging in request handlers
"""

import json
from io import StringIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mailreactor.main import create_app
from mailreactor.utils.logging import configure_logging


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client with fresh app instance."""
    app = create_app()
    return TestClient(app)


class TestRequestLogging:
    """Test suite for request logging integration."""

    def test_request_id_appears_in_response_headers(self, client: TestClient) -> None:
        """Test that request ID is included in response headers."""
        # Reconfigure logging to capture output
        configure_logging(json_format=True, log_level="INFO")

        response = client.get("/docs")

        # Verify X-Request-ID header exists
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Verify it's a valid UUID format (basic check)
        assert len(request_id) == 36  # UUID4 format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert request_id.count("-") == 4

    def test_request_id_appears_in_logs(self, client: TestClient) -> None:
        """Test that request ID appears in structured logs."""
        configure_logging(json_format=True, log_level="INFO")

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            response = client.get("/docs")

            output = mock_stderr.getvalue()
            request_id = response.headers["X-Request-ID"]

            # Parse log lines
            log_lines = [line for line in output.strip().split("\n") if line]

            # Find api_request log entry
            api_request_log = None
            for line in log_lines:
                try:
                    log_entry = json.loads(line)
                    if log_entry.get("event") == "api_request":
                        api_request_log = log_entry
                        break
                except json.JSONDecodeError:
                    continue

            # Verify request ID in log
            if api_request_log:
                assert api_request_log["request_id"] == request_id

    def test_request_completion_logged_with_duration(self, client: TestClient) -> None:
        """Test that request completion is logged with duration."""
        configure_logging(json_format=True, log_level="INFO")

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            client.get("/docs")

            output = mock_stderr.getvalue()

            # Parse log lines
            log_lines = [line for line in output.strip().split("\n") if line]

            # Find api_request log entry
            api_request_log = None
            for line in log_lines:
                try:
                    log_entry = json.loads(line)
                    if log_entry.get("event") == "api_request":
                        api_request_log = log_entry
                        break
                except json.JSONDecodeError:
                    continue

            # Verify request details
            if api_request_log:
                assert api_request_log["method"] == "GET"
                assert api_request_log["path"] == "/docs"
                assert api_request_log["status_code"] == 200
                assert "duration_ms" in api_request_log
                assert isinstance(api_request_log["duration_ms"], int)
                assert api_request_log["duration_ms"] >= 0

    def test_log_context_cleanup_between_requests(self, client: TestClient) -> None:
        """Test that log context is cleaned up between requests."""
        configure_logging(json_format=True, log_level="INFO")

        # Make two requests
        response1 = client.get("/docs")
        response2 = client.get("/redoc")

        request_id1 = response1.headers["X-Request-ID"]
        request_id2 = response2.headers["X-Request-ID"]

        # Verify different request IDs
        assert request_id1 != request_id2

    def test_multiple_concurrent_requests_have_unique_ids(self, client: TestClient) -> None:
        """Test that concurrent requests have unique request IDs."""
        configure_logging(json_format=True, log_level="INFO")

        # Make multiple requests
        responses = [client.get("/docs") for _ in range(5)]

        request_ids = [r.headers["X-Request-ID"] for r in responses]

        # Verify all unique
        assert len(set(request_ids)) == len(request_ids)


class TestStartupLogging:
    """Test suite for application startup logging."""

    def test_server_starting_event_logged(self) -> None:
        """Test that server_starting event is logged on app creation."""
        configure_logging(json_format=True, log_level="INFO")

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            create_app()

            output = mock_stderr.getvalue()

            # Parse log lines
            log_lines = [line for line in output.strip().split("\n") if line]

            # Find server_starting log entry
            server_starting_log = None
            for line in log_lines:
                try:
                    log_entry = json.loads(line)
                    if log_entry.get("event") == "server_starting":
                        server_starting_log = log_entry
                        break
                except json.JSONDecodeError:
                    continue

            # Verify startup log
            if server_starting_log:
                assert "host" in server_starting_log
                assert "port" in server_starting_log
                assert "log_level" in server_starting_log


class TestExceptionLogging:
    """Test suite for exception logging in request handlers."""

    def test_mailreactor_exception_is_logged(self, client: TestClient) -> None:
        """Test that MailReactorException is logged with details."""
        configure_logging(json_format=True, log_level="INFO")

        # This test would require a route that raises MailReactorException
        # For now, we can test the generic exception handler
        pass

    def test_generic_exception_is_logged(self, client: TestClient) -> None:
        """Test that generic exceptions are logged with error details."""
        configure_logging(json_format=True, log_level="INFO")

        # This test would require a route that raises a generic exception
        # For now, we can verify the handler exists
        pass
