"""Health check endpoint for monitoring and deployment validation.

This module provides a lightweight /health endpoint that:
- Returns system status, version, and uptime
- Responds in under 50ms at p95 (NFR-P2)
- Requires no authentication (always accessible for monitoring)
- Logged by middleware at INFO level (consistent with all endpoints)

The health endpoint is the monitoring canary - it should never return 500.
"""

from datetime import datetime

from fastapi import APIRouter, Request

from mailreactor.models.responses import HealthResponse, SuccessResponse
from mailreactor.utils.version import get_app_version


# Module-level start time for uptime calculation
# Set once at module import, survives for the application lifetime
_app_start_time: datetime = datetime.utcnow()


router = APIRouter()


@router.get(
    "/health",
    response_model=SuccessResponse[HealthResponse],
    status_code=200,
    summary="Check API health and uptime",
    description="Returns system status, version, and uptime. No authentication required.",
    tags=["System"],
)  # type: ignore[misc]
async def get_health(request: Request) -> SuccessResponse[HealthResponse]:
    """Check API health and uptime.

    Returns system status, version, and uptime in seconds.
    Timestamp is provided in meta.timestamp (no duplication in data).
    No authentication required - always accessible for monitoring.

    Returns:
        SuccessResponse[HealthResponse] with current system status
    """
    # Calculate uptime from module-level start time
    # Simple subtraction - no I/O, no external calls, no database queries
    uptime = (datetime.utcnow() - _app_start_time).total_seconds()

    health_data = HealthResponse(
        status="healthy",  # MVP: always healthy (no subsystems to check yet)
        version=get_app_version(),
        uptime_seconds=uptime,
    )

    # Get request_id from existing middleware (stored in request.state)
    request_id = request.state.request_id

    # Use factory method to wrap in envelope with auto-generated timestamp
    return SuccessResponse.create(data=health_data, request_id=request_id)
