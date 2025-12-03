"""
Performance tests for API response latency.

Validates NFR-P2: API response <200ms p95 (excluding IMAP/SMTP latency).

These tests measure API endpoint latency with mocked external services.
"""

import pytest


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_health_endpoint_latency_placeholder(api_client, benchmark):
    """
    Measure /health endpoint latency (NFR-P2).

    Health check should respond in <50ms p95.
    This will be implemented after Story 1.5 (Health Check Endpoint).
    """
    pytest.skip("Health endpoint not yet implemented (Story 1.5)")

    # Future implementation:
    # async def health_check():
    #     response = await api_client.get("/health")
    #     return response
    #
    # # Run benchmark
    # result = await benchmark.pedantic(health_check, rounds=100, iterations=1)
    #
    # # Extract latencies
    # latencies = benchmark.stats.stats.data
    # p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    #
    # # NFR-P2: Health check <50ms p95
    # assert p95 < 0.05, f"Health endpoint p95 too slow: {p95*1000:.1f}ms (target: <50ms)"


@pytest.mark.benchmark
@pytest.mark.performance
@pytest.mark.asyncio
async def test_api_endpoint_latency_placeholder(api_client, mock_async_imap_client, benchmark):
    """
    Measure typical API endpoint latency with mocked IMAP (NFR-P2).

    API endpoints should respond in <200ms p95 when external services are mocked.
    This will be implemented after Story 2.5 (Account Listing API).
    """
    pytest.skip("Account API not yet implemented (Story 2.5)")

    # Future implementation:
    # # Mock IMAP to remove network latency
    # mock_async_imap_client.list_accounts.return_value = []
    #
    # async def get_accounts():
    #     response = await api_client.get("/accounts")
    #     return response
    #
    # # Run benchmark
    # result = await benchmark.pedantic(get_accounts, rounds=100, iterations=1)
    #
    # # Extract latencies
    # latencies = benchmark.stats.stats.data
    # p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    #
    # # NFR-P2: API endpoints <200ms p95 (with mocked dependencies)
    # assert p95 < 0.2, f"API endpoint p95 too slow: {p95*1000:.1f}ms (target: <200ms)"
