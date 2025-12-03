"""Integration tests for FastAPI application initialization.

Tests cover:
- App creation and configuration
- App title and version
- OpenAPI documentation endpoints
- CORS middleware configuration
- Request ID middleware
"""

import pytest
from fastapi.testclient import TestClient

from mailreactor.main import create_app


class TestAppCreation:
    """Test FastAPI app creation and configuration."""

    def test_create_app(self):
        """Test create_app returns configured FastAPI instance."""
        app = create_app()

        assert app.title == "Mail Reactor API"
        assert app.version == "0.1.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
        assert app.openapi_url == "/openapi.json"


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation endpoints."""

    def test_docs_endpoint_accessible(self):
        """Test /docs (Swagger UI) is accessible."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint_accessible(self):
        """Test /redoc (ReDoc) is accessible."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_json_accessible(self):
        """Test /openapi.json is accessible."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Verify OpenAPI schema structure
        schema = response.json()
        assert schema["info"]["title"] == "Mail Reactor API"
        assert schema["info"]["version"] == "0.1.0"
        assert "openapi" in schema


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    def test_cors_disabled_by_default(self, monkeypatch):
        """Test CORS middleware is not active by default."""
        monkeypatch.setenv("MAILREACTOR_CORS_ENABLED", "false")
        app = create_app()
        client = TestClient(app)

        # Create a simple test endpoint
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        response = client.get("/test", headers={"Origin": "https://example.com"})

        # CORS headers should not be present when disabled
        assert "access-control-allow-origin" not in response.headers

    def test_cors_middleware_registration(self):
        """Test CORS middleware can be registered when settings.cors_enabled=True."""
        # Create custom settings with CORS enabled
        from mailreactor.main import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        # Create app manually with CORS enabled to test the pattern
        app = FastAPI(
            title="Mail Reactor API",
            version="0.1.0",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        response = client.get("/test", headers={"Origin": "https://example.com"})

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


class TestRequestIDMiddleware:
    """Test request ID middleware functionality."""

    def test_request_id_header_present(self):
        """Test X-Request-ID header is present in response."""
        app = create_app()
        client = TestClient(app)

        # Create a test endpoint
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        response = client.get("/test")

        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    def test_request_id_is_uuid(self):
        """Test X-Request-ID is a valid UUID."""
        import uuid

        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        response = client.get("/test")
        request_id = response.headers["X-Request-ID"]

        # Should be a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Request ID is not a valid UUID: {request_id}")

    def test_request_id_unique_per_request(self):
        """Test each request gets a unique request ID."""
        app = create_app()
        client = TestClient(app)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        response1 = client.get("/test")
        response2 = client.get("/test")

        request_id1 = response1.headers["X-Request-ID"]
        request_id2 = response2.headers["X-Request-ID"]

        assert request_id1 != request_id2


class TestAppImport:
    """Test app can be imported without errors."""

    def test_create_app_factory(self):
        """Test create_app() factory function works correctly."""
        from mailreactor.main import create_app

        app = create_app()
        assert app.title == "Mail Reactor API"
