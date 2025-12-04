"""Integration tests for health check endpoint (Story 1.7 updated).

Tests cover:
- GET /health returns 200 OK
- SuccessResponse envelope format with data and meta
- Response schema validation
- request_id in meta matches X-Request-ID header
- Timestamp in ISO 8601 UTC format
- Uptime increases over time
- No authentication required
- Middleware logging
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
    """Test health check endpoint basic functionality with SuccessResponse envelope."""

    def test_health_response_envelope_structure(self, client):
        """Test response follows SuccessResponse[HealthResponse] envelope format."""
        response = client.get("/health")
        data = response.json()

        # Verify SuccessResponse envelope structure
        assert "data" in data
        assert "meta" in data

        # Verify meta fields
        assert "request_id" in data["meta"]
        assert "timestamp" in data["meta"]

        # Verify data (HealthResponse) fields
        assert "status" in data["data"]
        assert "version" in data["data"]
        assert "uptime_seconds" in data["data"]
        # Timestamp only in meta, not duplicated in data
        assert "timestamp" not in data["data"]

    def test_health_response_schema(self, client):
        """Test HealthResponse data includes all required fields with correct types."""
        response = client.get("/health")
        json_data = response.json()
        data = json_data["data"]
        meta = json_data["meta"]

        # Verify data field types
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["uptime_seconds"], (int, float))

        # Verify timestamp only in meta
        assert "timestamp" not in data
        assert isinstance(meta["timestamp"], str)

    def test_health_status_is_healthy(self, client):
        """Test health endpoint returns 'healthy' status."""
        response = client.get("/health")
        data = response.json()["data"]

        assert data["status"] == "healthy"

    def test_health_version_is_present(self, client):
        """Test health endpoint returns version string."""
        response = client.get("/health")
        data = response.json()["data"]

        # Version should be non-empty string in semantic versioning format
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0
        assert data["version"][0].isdigit()  # Starts with digit

    def test_health_uptime_is_positive(self, client):
        """Test uptime_seconds is a positive number."""
        response = client.get("/health")
        data = response.json()["data"]

        assert data["uptime_seconds"] >= 0

    def test_health_uptime_is_reasonable(self, client):
        """Test uptime is reasonable (not absurdly large)."""
        response = client.get("/health")
        data = response.json()["data"]

        # Should be less than 1 hour for test execution
        assert data["uptime_seconds"] < 3600


class TestHealthEndpointBehavior:
    """Test health endpoint behavioral requirements."""

    def test_health_uptime_increases(self, client):
        """Test uptime increases with subsequent requests."""
        # First request
        response1 = client.get("/health")
        uptime1 = response1.json()["data"]["uptime_seconds"]

        # Wait a bit
        time.sleep(0.1)

        # Second request
        response2 = client.get("/health")
        uptime2 = response2.json()["data"]["uptime_seconds"]

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
        assert all(r.json()["data"]["uptime_seconds"] >= 0 for r in responses)


class TestSuccessResponseEnvelope:
    """Test SuccessResponse envelope format (Story 1.7)."""

    def test_request_id_in_meta_matches_header(self, client):
        """Test meta.request_id matches X-Request-ID response header."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        data = response.json()
        meta_request_id = data["meta"]["request_id"]
        header_request_id = response.headers["X-Request-ID"]

        assert meta_request_id == header_request_id

    def test_request_id_unique_per_request(self, client):
        """Test different requests get different request_ids."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        id1 = response1.json()["meta"]["request_id"]
        id2 = response2.json()["meta"]["request_id"]

        assert id1 != id2

    def test_timestamp_is_iso_8601_utc_format(self, client):
        """Test meta.timestamp is ISO 8601 UTC format."""
        response = client.get("/health")
        data = response.json()

        timestamp = data["meta"]["timestamp"]

        # ISO 8601 format check (basic validation)
        assert isinstance(timestamp, str)
        # Should contain T separator and Z suffix or +00:00
        assert "T" in timestamp
        # Pydantic serializes with Z or +00:00 for UTC
        assert timestamp.endswith("Z") or "+00:00" in timestamp

    def test_meta_request_id_is_uuid_format(self, client):
        """Test meta.request_id is valid UUID4 format."""
        response = client.get("/health")
        data = response.json()

        request_id = data["meta"]["request_id"]

        # UUID4 format: 8-4-4-4-12 hexadecimal characters
        assert isinstance(request_id, str)
        assert len(request_id) == 36  # UUID with dashes
        assert request_id.count("-") == 4


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
