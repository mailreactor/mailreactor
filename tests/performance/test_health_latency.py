"""Performance tests for health check endpoint.

Tests NFR-P2: Health endpoint must respond within 50ms at p95 percentile.

These tests measure actual response times and validate performance targets.
"""

import statistics
import time

import pytest
from fastapi.testclient import TestClient

from mailreactor.main import create_app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpointPerformance:
    """Test health endpoint performance requirements (NFR-P2)."""

    def test_health_endpoint_response_time_p95(self, client):
        """Test health endpoint responds within 50ms at p95 percentile (NFR-P2).

        This is a critical performance requirement for monitoring systems.
        Health checks are polled frequently, so they must be fast.
        """
        num_requests = 100
        response_times = []

        # Warm-up request (not counted)
        client.get("/health")

        # Measure response times
        for _ in range(num_requests):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()

            assert response.status_code == 200
            response_times.append((end - start) * 1000)  # Convert to milliseconds

        # Calculate p95 latency
        p95_latency = statistics.quantiles(response_times, n=100)[94]  # 95th percentile

        # Assert p95 is under 50ms (NFR-P2)
        assert p95_latency < 50, (
            f"Health endpoint p95 latency {p95_latency:.2f}ms exceeds 50ms target"
        )

    def test_health_endpoint_average_response_time(self, client):
        """Test health endpoint has low average response time."""
        num_requests = 50
        response_times = []

        # Warm-up
        client.get("/health")

        # Measure
        for _ in range(num_requests):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()

            assert response.status_code == 200
            response_times.append((end - start) * 1000)

        avg_latency = statistics.mean(response_times)

        # Average should be well under p95 target
        assert avg_latency < 25, f"Average latency {avg_latency:.2f}ms is too high"

    def test_health_endpoint_no_slow_outliers(self, client):
        """Test health endpoint has no extremely slow outliers."""
        num_requests = 50
        response_times = []

        for _ in range(num_requests):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()

            assert response.status_code == 200
            response_times.append((end - start) * 1000)

        max_latency = max(response_times)

        # Maximum should not exceed 100ms (2x the p95 target)
        assert max_latency < 100, f"Outlier response time {max_latency:.2f}ms is too slow"

    def test_health_endpoint_consistent_performance(self, client):
        """Test health endpoint has consistent performance (low variance)."""
        num_requests = 30
        response_times = []

        for _ in range(num_requests):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()

            assert response.status_code == 200
            response_times.append((end - start) * 1000)

        std_dev = statistics.stdev(response_times)

        # Standard deviation should be low (consistent performance)
        assert std_dev < 10, f"Performance variance too high: {std_dev:.2f}ms std dev"


class TestHealthEndpointConcurrentPerformance:
    """Test health endpoint performance under concurrent load."""

    def test_health_endpoint_sequential_requests_fast(self, client):
        """Test health endpoint maintains performance over sequential requests."""
        num_requests = 100
        slow_requests = []

        for i in range(num_requests):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()

            response_time_ms = (end - start) * 1000

            assert response.status_code == 200

            if response_time_ms > 50:
                slow_requests.append((i, response_time_ms))

        # Most requests should be fast (allow up to 10% to be slow)
        slow_percentage = (len(slow_requests) / num_requests) * 100

        assert slow_percentage < 10, f"{slow_percentage:.1f}% of requests exceeded 50ms target"
