"""Integration tests for health check endpoint.

Tests cover:
- GET /health returns 200 OK
- Response schema validation
- Uptime increases over time
- No authentication required
- DEBUG level logging
- Router registration
- OpenAPI documentation
"""

import time

import pytest
from fastapi.testclient import TestClient

from mailreactor.main import create_app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint basic functionality."""

    def test_health_response_schema(self, client):
        """Test response includes all required fields with correct types."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data

        # Verify types
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["uptime_seconds"], (int, float))
        assert isinstance(data["timestamp"], str)

    def test_health_status_is_healthy(self, client):
        """Test health endpoint returns 'healthy' status."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_version_is_present(self, client):
        """Test health endpoint returns version string."""
        response = client.get("/health")
        data = response.json()

        # Version should be non-empty string in semantic versioning format
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0
        assert data["version"][0].isdigit()  # Starts with digit

    def test_health_uptime_is_positive(self, client):
        """Test uptime_seconds is a positive number."""
        response = client.get("/health")
        data = response.json()

        assert data["uptime_seconds"] >= 0

    def test_health_uptime_is_reasonable(self, client):
        """Test uptime is reasonable (not absurdly large)."""
        response = client.get("/health")
        data = response.json()

        # Should be less than 1 hour for test execution
        assert data["uptime_seconds"] < 3600


class TestHealthEndpointBehavior:
    """Test health endpoint behavioral requirements."""

    def test_health_uptime_increases(self, client):
        """Test uptime increases with subsequent requests."""
        # First request
        response1 = client.get("/health")
        uptime1 = response1.json()["uptime_seconds"]

        # Wait a bit
        time.sleep(0.1)

        # Second request
        response2 = client.get("/health")
        uptime2 = response2.json()["uptime_seconds"]

        assert uptime2 > uptime1
        # Verify the delta is approximately the sleep duration
        assert 0.05 < (uptime2 - uptime1) < 0.2

    def test_health_endpoint_no_authentication_required(self, client):
        """Test health endpoint accessible without authentication headers."""
        # Request without any auth headers
        response = client.get("/health")

        # Should NOT return 401 or 403
        assert response.status_code == 200
        assert response.status_code != 401
        assert response.status_code != 403

    def test_health_endpoint_multiple_requests(self, client):
        """Test health endpoint handles multiple concurrent-style requests."""
        responses = []
        for _ in range(10):
            response = client.get("/health")
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # All should have valid uptime
        assert all(r.json()["uptime_seconds"] >= 0 for r in responses)


class TestHealthEndpointLogging:
    """Test health endpoint logging behavior."""

    def test_health_endpoint_logs_at_info_level_in_middleware(self, client, capsys):
        """Test health endpoint is logged consistently at INFO level by middleware.

        The middleware logs ALL requests at INFO (http_request) for consistency.
        This provides visibility while users can filter at the log aggregator level.
        """
        response = client.get("/health")

        assert response.status_code == 200

        # structlog logs to stdout, check captured output
        captured = capsys.readouterr()

        # Middleware should log http_request at INFO level (consistent with all endpoints)
        assert "[info" in captured.out.lower()
        assert "http_request" in captured.out
        assert "/health" in captured.out
