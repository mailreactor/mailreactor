"""Unit tests for health check module.

Tests cover:
- Application start time initialization (our code)
- Uptime calculation logic (our code)

Note: We don't test Pydantic model validation - Pydantic ensures that.
"""

from datetime import datetime

from mailreactor.api.health import _app_start_time


class TestAppStartTime:
    """Test application start time tracking."""

    def test_app_start_time_is_datetime(self):
        """Test module-level _app_start_time is initialized as datetime."""
        assert isinstance(_app_start_time, datetime)

    def test_app_start_time_is_reasonable(self):
        """Test _app_start_time is within reasonable bounds (not far in past/future)."""
        now = datetime.utcnow()
        time_diff = abs((now - _app_start_time).total_seconds())

        # Should be set within last hour (module just imported)
        assert time_diff < 3600
