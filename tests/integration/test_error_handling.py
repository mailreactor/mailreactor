"""Integration tests for exception handlers.

Tests cover:
- MailReactorException handler
- Generic Exception handler
- Error response format
- HTTP status code mapping
"""

from fastapi.testclient import TestClient

from mailreactor.main import create_app
from mailreactor.exceptions import (
    MailReactorException,
    AccountError,
    ConnectionError,
    AuthenticationError,
    MessageError,
    StateError,
)


class TestMailReactorExceptionHandler:
    """Test custom MailReactorException handler."""

    def test_mailreactor_exception_handler(self):
        """Test MailReactorException returns correct error envelope."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise MailReactorException("Test error", status_code=500)

        response = client.get("/test")

        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "MAILREACTOREXCEPTION",
                "message": "Test error",
            }
        }

    def test_account_error_handler(self):
        """Test AccountError returns 400 with correct format."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise AccountError("Account not found")

        response = client.get("/test")

        assert response.status_code == 400
        assert response.json() == {
            "error": {
                "code": "ACCOUNTERROR",
                "message": "Account not found",
            }
        }

    def test_connection_error_handler(self):
        """Test ConnectionError returns 503 with correct format."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise ConnectionError("Failed to connect to IMAP server")

        response = client.get("/test")

        assert response.status_code == 503
        assert response.json() == {
            "error": {
                "code": "CONNECTIONERROR",
                "message": "Failed to connect to IMAP server",
            }
        }

    def test_authentication_error_handler(self):
        """Test AuthenticationError returns 401 with correct format."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise AuthenticationError("Invalid credentials")

        response = client.get("/test")

        assert response.status_code == 401
        assert response.json() == {
            "error": {
                "code": "AUTHENTICATIONERROR",
                "message": "Invalid credentials",
            }
        }

    def test_message_error_handler(self):
        """Test MessageError returns 400 with correct format."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise MessageError("Invalid email format")

        response = client.get("/test")

        assert response.status_code == 400
        assert response.json() == {
            "error": {
                "code": "MESSAGEERROR",
                "message": "Invalid email format",
            }
        }

    def test_state_error_handler(self):
        """Test StateError returns 500 with correct format."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise StateError("Failed to save state")

        response = client.get("/test")

        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "STATEERROR",
                "message": "Failed to save state",
            }
        }


class TestGenericExceptionHandler:
    """Test generic Exception handler."""

    def test_generic_exception_handler(self):
        """Test generic Exception returns 500 with standard message."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Unexpected error")

        response = client.get("/test")

        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            }
        }

    def test_generic_exception_does_not_leak_details(self):
        """Test generic exception doesn't leak error details (security)."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        @app.get("/test")
        async def test_endpoint():
            raise RuntimeError("Sensitive internal error details")

        response = client.get("/test")

        # Should not contain the actual error message
        assert "Sensitive internal error details" not in response.text
        assert response.json()["error"]["message"] == "An unexpected error occurred"


class TestErrorResponseFormat:
    """Test error response format consistency."""

    def test_error_response_format(self):
        """Test error responses follow standard envelope format with uppercase codes."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise AccountError("Test error")

        response = client.get("/test")
        data = response.json()

        # Verify structure
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

        # Verify code is uppercase
        assert data["error"]["code"] == data["error"]["code"].upper()

        # Verify JSON content type
        assert "application/json" in response.headers["content-type"]


class TestHTTPStatusCodeMapping:
    """Test HTTP status code mapping for all exception types."""

    def test_all_exception_status_codes(self):
        """Test each exception type maps to correct HTTP status code."""
        app = create_app()
        client = TestClient(app)

        test_cases = [
            (AccountError("test"), 400),
            (ConnectionError("test"), 503),
            (AuthenticationError("test"), 401),
            (MessageError("test"), 400),
            (StateError("test"), 500),
        ]

        for exception, expected_status in test_cases:

            @app.get(f"/test-{expected_status}")
            async def test_endpoint():
                raise exception

            response = client.get(f"/test-{expected_status}")
            assert response.status_code == expected_status, (
                f"{exception.__class__.__name__} should return {expected_status}"
            )
