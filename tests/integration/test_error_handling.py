"""Integration tests for exception handlers (Story 1.7 updated).

Tests cover:
- MailReactorException handler with Pydantic ErrorResponse
- Generic Exception handler with Pydantic ErrorResponse
- RequestValidationError handler with field-specific details
- Error response format with details field
- HTTP status code mapping
"""

from fastapi.testclient import TestClient
from pydantic import BaseModel

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
        """Test MailReactorException returns correct ErrorResponse Pydantic model."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise MailReactorException("Test error", status_code=500)

        response = client.get("/test")

        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "MAILREACTOREXCEPTION"
        assert data["error"]["message"] == "Test error"
        assert data["error"]["details"] is None

    def test_account_error_handler(self):
        """Test AccountError returns 400 with correct Pydantic model structure."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise AccountError("Account not found")

        response = client.get("/test")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "ACCOUNTERROR"
        assert data["error"]["message"] == "Account not found"
        assert data["error"]["details"] is None

    def test_connection_error_handler(self):
        """Test ConnectionError returns 503 with correct Pydantic model structure."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise ConnectionError("Failed to connect to IMAP server")

        response = client.get("/test")

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "CONNECTIONERROR"
        assert data["error"]["message"] == "Failed to connect to IMAP server"
        assert data["error"]["details"] is None

    def test_authentication_error_handler(self):
        """Test AuthenticationError returns 401 with correct Pydantic model structure."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise AuthenticationError("Invalid credentials")

        response = client.get("/test")

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATIONERROR"
        assert data["error"]["message"] == "Invalid credentials"
        assert data["error"]["details"] is None

    def test_message_error_handler(self):
        """Test MessageError returns 400 with correct Pydantic model structure."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise MessageError("Invalid email format")

        response = client.get("/test")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "MESSAGEERROR"
        assert data["error"]["message"] == "Invalid email format"
        assert data["error"]["details"] is None

    def test_state_error_handler(self):
        """Test StateError returns 500 with correct Pydantic model structure."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise StateError("Failed to save state")

        response = client.get("/test")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "STATEERROR"
        assert data["error"]["message"] == "Failed to save state"
        assert data["error"]["details"] is None


class TestGenericExceptionHandler:
    """Test generic Exception handler."""

    def test_generic_exception_handler(self):
        """Test generic Exception returns 500 with ErrorResponse Pydantic model."""
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Unexpected error")

        response = client.get("/test")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "An unexpected error occurred"
        assert data["error"]["details"] is None

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


class TestRequestValidationErrorHandler:
    """Test RequestValidationError handler (Story 1.7)."""

    def test_request_validation_error_handler(self):
        """Test FastAPI validation error returns 400 with field-specific details."""
        app = create_app()
        client = TestClient(app)

        # Define test model with validation
        class TestModel(BaseModel):
            email: str
            age: int

        @app.post("/test")
        async def test_endpoint(data: TestModel):
            return {"status": "ok"}

        # Send invalid data (missing required fields)
        response = client.post("/test", json={})

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Invalid request parameters"
        assert "details" in data["error"]
        assert "errors" in data["error"]["details"]
        assert len(data["error"]["details"]["errors"]) > 0

    def test_validation_error_includes_field_details(self):
        """Test validation error details include field-specific information."""
        app = create_app()
        client = TestClient(app)

        class TestModel(BaseModel):
            count: int

        @app.post("/test")
        async def test_endpoint(data: TestModel):
            return {"status": "ok"}

        # Send invalid type
        response = client.post("/test", json={"count": "not-a-number"})

        assert response.status_code == 400
        data = response.json()
        errors = data["error"]["details"]["errors"]

        # Check that error details contain location information
        assert any("count" in str(err.get("loc", [])) for err in errors)


class TestErrorResponseFormat:
    """Test error response format consistency."""

    def test_error_response_format(self):
        """Test error responses follow ErrorResponse Pydantic model structure."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            raise AccountError("Test error")

        response = client.get("/test")
        data = response.json()

        # Verify ErrorResponse structure with ErrorDetail
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]

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
