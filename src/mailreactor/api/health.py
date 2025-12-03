"""Health check endpoint for monitoring and deployment validation.

This module provides a lightweight /health endpoint that:
- Returns system status, version, and uptime
- Responds in under 50ms at p95 (NFR-P2)
- Requires no authentication (always accessible for monitoring)
- Logged by middleware at INFO level (consistent with all endpoints)

The health endpoint is the monitoring canary - it should never return 500.
"""

from datetime import datetime

from fastapi import APIRouter

from mailreactor.models.responses import HealthResponse
from mailreactor.utils.version import get_app_version


# Module-level start time for uptime calculation
# Set once at module import, survives for the application lifetime
_app_start_time: datetime = datetime.utcnow()


router = APIRouter()


@router.get("/health", response_model=HealthResponse)  # type: ignore[misc]
async def get_health() -> HealthResponse:
    """Check API health and uptime.

    Returns system status, version, and uptime in seconds.
    This endpoint is always accessible without authentication.

    The health endpoint should never return 500 - it's the monitoring canary.
    Response time target: <50ms at p95 percentile (NFR-P2).

    Returns:
        HealthResponse with current system status

    Examples:
        >>> # Via HTTP
        >>> # GET /health
        >>> # Response: {"status": "healthy", "version": "0.1.0", "uptime_seconds": 42.5, ...}
    """
    # Calculate uptime from module-level start time
    # Simple subtraction - no I/O, no external calls, no database queries
    uptime = (datetime.utcnow() - _app_start_time).total_seconds()

    return HealthResponse(
        status="healthy",  # MVP: always healthy (no subsystems to check yet)
        version=get_app_version(),
        uptime_seconds=uptime,
        timestamp=datetime.utcnow(),
    )
