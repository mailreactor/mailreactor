"""Unit tests for response models (Story 1.7).

Tests our response model serialization and factory methods.
Following hc-standards: ONLY test functionality WE have added.
"""

from datetime import datetime, timezone


from mailreactor.models.responses import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ResponseMeta,
    SuccessResponse,
)


class TestResponseMeta:
    """Test ResponseMeta model serialization."""

    def test_response_meta_serialization(self):
        """Test ResponseMeta serializes to correct JSON structure."""
        meta = ResponseMeta(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            timestamp=datetime(2025, 12, 4, 10, 30, 45, tzinfo=timezone.utc),
        )

        data = meta.model_dump()

        assert data["request_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert "timestamp" in data

    def test_response_meta_json_schema_includes_examples(self):
        """Test ResponseMeta schema includes example for OpenAPI docs."""
        schema = ResponseMeta.model_json_schema()

        assert "example" in schema
        assert "request_id" in schema["example"]
        assert "timestamp" in schema["example"]


class TestErrorDetail:
    """Test ErrorDetail model serialization."""

    def test_error_detail_serialization_without_details(self):
        """Test ErrorDetail with no details field."""
        error = ErrorDetail(
            code="ACCOUNT_NOT_FOUND", message="Account acc_123 not found", details=None
        )

        data = error.model_dump()

        assert data["code"] == "ACCOUNT_NOT_FOUND"
        assert data["message"] == "Account acc_123 not found"
        assert data["details"] is None

    def test_error_detail_serialization_with_details(self):
        """Test ErrorDetail with validation error details."""
        error = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid request parameters",
            details={"errors": [{"loc": ["body", "email"], "msg": "invalid email"}]},
        )

        data = error.model_dump()

        assert data["code"] == "VALIDATION_ERROR"
        assert data["message"] == "Invalid request parameters"
        assert "errors" in data["details"]
        assert len(data["details"]["errors"]) == 1

    def test_error_detail_json_schema_includes_examples(self):
        """Test ErrorDetail schema includes example for OpenAPI docs."""
        schema = ErrorDetail.model_json_schema()

        assert "example" in schema
        assert schema["example"]["code"] == "ACCOUNT_NOT_FOUND"


class TestErrorResponse:
    """Test ErrorResponse envelope model."""

    def test_error_response_serialization(self):
        """Test ErrorResponse wraps ErrorDetail correctly."""
        error_detail = ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            details=None,
        )
        response = ErrorResponse(error=error_detail)

        data = response.model_dump()

        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "An unexpected error occurred"

    def test_error_response_json_schema_includes_examples(self):
        """Test ErrorResponse schema includes example for OpenAPI docs."""
        schema = ErrorResponse.model_json_schema()

        assert "example" in schema
        assert "error" in schema["example"]
        assert schema["example"]["error"]["code"] == "VALIDATION_ERROR"


class TestSuccessResponse:
    """Test SuccessResponse generic envelope model."""

    def test_success_response_with_health_data(self):
        """Test SuccessResponse[HealthResponse] preserves generic type."""
        health_data = HealthResponse(
            status="healthy",
            version="0.1.0",
            uptime_seconds=123.45,
        )
        meta = ResponseMeta(request_id="test-id", timestamp=datetime.now(timezone.utc))
        response = SuccessResponse[HealthResponse](data=health_data, meta=meta)

        data = response.model_dump()

        assert "data" in data
        assert "meta" in data
        assert data["data"]["status"] == "healthy"
        assert data["data"]["version"] == "0.1.0"
        assert data["meta"]["request_id"] == "test-id"
        # Timestamp only in meta, not in data
        assert "timestamp" not in data["data"]
        assert "timestamp" in data["meta"]

    def test_success_response_create_factory_generates_timestamp(self):
        """Test SuccessResponse.create() factory method generates current timestamp in meta."""
        health_data = HealthResponse(
            status="healthy",
            version="0.1.0",
            uptime_seconds=123.45,
        )

        before = datetime.now(timezone.utc)
        response = SuccessResponse.create(data=health_data, request_id="test-id")
        after = datetime.now(timezone.utc)

        assert response.meta.request_id == "test-id"
        assert before <= response.meta.timestamp <= after

    def test_success_response_create_uses_utc_timezone(self):
        """Test SuccessResponse.create() uses UTC timezone for meta timestamp."""
        health_data = HealthResponse(
            status="healthy",
            version="0.1.0",
            uptime_seconds=123.45,
        )

        response = SuccessResponse.create(data=health_data, request_id="test-id")

        # Pydantic serializes datetime to ISO 8601 string
        assert response.meta.timestamp.tzinfo == timezone.utc
