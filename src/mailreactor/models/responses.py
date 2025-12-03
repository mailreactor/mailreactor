"""Response models for API endpoints.

This module defines Pydantic models for API responses:
- HealthResponse: Health check endpoint response (Story 1.5)
- Future: SuccessResponse[T], ErrorResponse (Story 1.7)
"""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: System health status ("healthy", "degraded", "unhealthy")
        version: Application version string
        uptime_seconds: Time since application start in seconds
        timestamp: Current UTC timestamp

    Examples:
        >>> response = HealthResponse(
        ...     status="healthy",
        ...     version="0.1.0",
        ...     uptime_seconds=123.45,
        ...     timestamp=datetime.utcnow()
        ... )
        >>> response.status
        'healthy'
    """

    status: str = Field(
        ...,
        description="System health status: healthy, degraded, or unhealthy",
        examples=["healthy"],
    )
    version: str = Field(..., description="Application version", examples=["0.1.0"])
    uptime_seconds: float = Field(
        ..., description="Time since application start in seconds", examples=[123.45]
    )
    timestamp: datetime = Field(
        ..., description="Current UTC timestamp", examples=["2025-12-03T10:30:00"]
    )
