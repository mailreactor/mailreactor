"""
Performance tests for Mail Reactor startup time.

Validates NFR-P1: Startup time <3 seconds (cold start to operational).

These tests use pytest-benchmark to measure and track performance over time.
"""

import pytest


@pytest.mark.benchmark
@pytest.mark.performance
def test_import_time(benchmark):
    """
    Measure import time for mailreactor package.

    This is a proxy for startup time until the main app is implemented.
    Target: <500ms for imports.
    """

    def import_mailreactor():
        # Lazy import to measure fresh import time
        import sys

        # Remove from cache to get true import time
        if "mailreactor" in sys.modules:
            del sys.modules["mailreactor"]

        import mailreactor

        return mailreactor

    benchmark(import_mailreactor)

    # Imports should be fast (<500ms)
    # This is much stricter than the 3s startup NFR
    assert benchmark.stats.stats.median < 0.5, (
        f"Import time too slow: {benchmark.stats.stats.median:.3f}s (target: <0.5s)"
    )


@pytest.mark.benchmark
@pytest.mark.performance
def test_startup_time_placeholder(benchmark):
    """
    Measure cold start time from import to operational (NFR-P1).

    This will be implemented after Story 1.4 (CLI Start Command).
    Target: <3 seconds median, <3.5 seconds max.
    """
    pytest.skip("Application startup not yet implemented (Story 1.4)")

    # Future implementation:
    # def startup():
    #     # Import and initialize FastAPI app
    #     from mailreactor.main import app
    #     from mailreactor.cli import start_server
    #
    #     # Trigger startup events
    #     # This simulates the full application startup
    #     return app
    #
    # result = benchmark(startup)
    #
    # # NFR-P1: Median startup time <3 seconds
    # assert benchmark.stats.stats.median < 3.0, (
    #     f"Startup too slow: {benchmark.stats.stats.median:.3f}s (target: <3.0s)"
    # )
    #
    # # Allow some variance, but max should be <3.5s
    # assert benchmark.stats.stats.max < 3.5, (
    #     f"Max startup too slow: {benchmark.stats.stats.max:.3f}s (target: <3.5s)"
    # )


@pytest.mark.benchmark
@pytest.mark.performance
def test_config_loading_speed(benchmark):
    """
    Measure configuration loading time.

    Config loading should be nearly instant (<50ms).
    This will be implemented when Settings/Config is added.
    """
    pytest.skip("Configuration loading not yet implemented")

    # Future implementation:
    # from mailreactor.config import load_settings
    #
    # def load_config():
    #     return load_settings()
    #
    # result = benchmark(load_config)
    #
    # # Config loading should be very fast
    # assert benchmark.stats.stats.median < 0.05, (
    #     f"Config loading too slow: {benchmark.stats.stats.median:.3f}s (target: <0.05s)"
    # )
