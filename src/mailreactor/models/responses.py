"""Response models for API endpoints.

This module defines Pydantic models for API responses:
- HealthResponse: Health check endpoint response (Story 1.5)
- SuccessResponse[T]: Generic success envelope with data and meta (Story 1.7)
- ErrorResponse: Standard error envelope (Story 1.7)
- ErrorDetail: Error structure with code, message, details (Story 1.7)
- ResponseMeta: Metadata with request_id and timestamp (Story 1.7)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# Story 1.5: Health check response model
# Timestamp provided in envelope's meta.timestamp (not duplicated here)
class HealthResponse(BaseModel):
    status: str = Field(
        ...,
        description="System health status: healthy, degraded, or unhealthy",
        examples=["healthy"],
    )
    version: str = Field(..., description="Application version", examples=["0.1.0"])
    uptime_seconds: float = Field(
        ..., description="Time since application start in seconds", examples=[123.45]
    )


# Story 1.7: Response metadata (request_id from middleware, timestamp auto-generated)
class ResponseMeta(BaseModel):
    request_id: str = Field(
        ...,
        description="Unique request identifier for tracing",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    timestamp: datetime = Field(
        ...,
        description="Response timestamp in UTC (ISO 8601)",
        examples=["2025-12-04T10:30:45Z"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-12-04T10:30:45Z",
            }
        }
    )


# Story 1.7: Generic success envelope wrapping all successful responses
class SuccessResponse(BaseModel, Generic[T]):
    data: T = Field(..., description="Response data")
    meta: ResponseMeta = Field(..., description="Response metadata")

    @classmethod
    def create(cls, data: T, request_id: str) -> "SuccessResponse[T]":
        """Factory method to create success response with current timestamp."""
        return cls(
            data=data,
            meta=ResponseMeta(request_id=request_id, timestamp=datetime.now(timezone.utc)),
        )


# Story 1.7: Error detail structure with code, message, and optional details
class ErrorDetail(BaseModel):
    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["ACCOUNT_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Account acc_123 not found"],
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error context (validation errors, field details)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "ACCOUNT_NOT_FOUND",
                "message": "Account acc_123 not found",
                "details": None,
            }
        }
    )


# Story 1.7: Standard error envelope wrapping all error responses
class ErrorResponse(BaseModel):
    error: ErrorDetail = Field(..., description="Error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "details": {
                        "errors": [
                            {
                                "loc": ["body", "email"],
                                "msg": "value is not a valid email address",
                                "type": "value_error.email",
                            }
                        ]
                    },
                }
            }
        }
    )
