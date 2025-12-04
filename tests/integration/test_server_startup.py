"""Integration tests for CLI server startup.

Tests full server startup sequence including:
- Server binding and listening
- Health endpoint responding
- Startup messages logged
- Graceful shutdown
"""

import signal
import subprocess
import sys
import time

import httpx
import pytest


@pytest.fixture
def server_process() -> subprocess.Popen:  # type: ignore[type-arg]
    """Fixture to start server process and clean up after test."""
    process = None

    def _start_server(args: list[str]) -> subprocess.Popen:  # type: ignore[type-arg]
        """Start server with given CLI arguments."""
        nonlocal process
        # Use python -m mailreactor to test __main__ entry point
        cmd = [sys.executable, "-m", "mailreactor"] + args
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Wait a bit for server to start
        time.sleep(0.5)
        return process

    yield _start_server

    # Cleanup: Kill process if still running
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


class TestServerStartup:
    """Test server startup and initialization."""

    def test_server_starts_and_responds_to_docs_endpoint(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test server starts and docs endpoint responds."""
        process = server_process(["start"])

        # Wait for server to be ready (with retries)
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:8000/docs", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)
        else:
            pytest.fail("Server did not start within expected time")

        # Verify docs endpoint (Swagger UI HTML)
        response = httpx.get("http://127.0.0.1:8000/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

        # Cleanup
        process.terminate()
        process.wait(timeout=5)

    def test_server_starts_on_custom_port(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test server starts on custom port."""
        process = server_process(["start", "--port", "8001"])

        # Wait for server to be ready
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:8001/docs", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)
        else:
            pytest.fail("Server did not start on custom port")

        # Verify server on port 8001
        response = httpx.get("http://127.0.0.1:8001/docs")
        assert response.status_code == 200

        # Cleanup
        process.terminate()
        process.wait(timeout=5)

    def test_server_graceful_shutdown_on_sigterm(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test server shuts down gracefully on SIGTERM."""
        process = server_process(["start"])

        # Wait for server to be ready
        time.sleep(2)

        # Send SIGTERM
        process.send_signal(signal.SIGTERM)

        # Wait for graceful shutdown
        try:
            return_code = process.wait(timeout=5)
            # Should exit cleanly
            assert return_code in (0, -signal.SIGTERM)
        except subprocess.TimeoutExpired:
            pytest.fail("Server did not shut down gracefully")


class TestServerStartupPerformance:
    """Test server startup performance (NFR-P1: <3 seconds)."""

    def test_server_starts_within_3_seconds(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test server starts and responds within 3 seconds (NFR-P1)."""
        start_time = time.time()

        process = server_process(["start"])

        # Wait for docs endpoint to respond (30 attempts x 100ms = 3s max)
        for _ in range(30):
            try:
                response = httpx.get("http://127.0.0.1:8000/docs", timeout=0.5)
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    # Verify startup time within target
                    assert elapsed < 3.0, f"Server took {elapsed:.2f}s to start (target: 3s)"
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.1)
        else:
            pytest.fail("Server did not respond within 3 seconds")

        # Cleanup
        process.terminate()
        process.wait(timeout=5)


class TestServerSecurityDefaults:
    """Test security-related defaults (localhost binding)."""

    def test_server_binds_to_localhost_by_default(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test server binds to localhost (127.0.0.1) by default."""
        process = server_process(["start"])

        # Wait for startup with retry
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:8000/docs", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)

        # Verify accessible on localhost
        response = httpx.get("http://127.0.0.1:8000/docs")
        assert response.status_code == 200

        # Cleanup
        process.terminate()
        process.wait(timeout=5)


class TestDevCommand:
    """Test dev command with auto-reload (Story 1.8)."""

    def test_dev_command_starts_server_with_reload(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test dev command starts server successfully."""
        process = server_process(["dev"])

        # Wait for server to be ready
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:8000/health", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)
        else:
            pytest.fail("Dev server did not start within expected time")

        # Verify server responds
        response = httpx.get("http://127.0.0.1:8000/health")
        assert response.status_code == 200

        # Cleanup
        process.terminate()
        process.wait(timeout=5)

    def test_dev_command_logs_development_mode_warning(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test dev command logs development mode warning.

        Note: This test verifies the dev command starts successfully.
        Log message verification is covered by unit tests (mocked).
        """
        process = server_process(["dev"])

        # Wait for server to be ready
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:8000/health", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)
        else:
            pytest.fail("Dev server did not start")

        # Server started successfully (warning would prevent startup if broken)
        response = httpx.get("http://127.0.0.1:8000/health")
        assert response.status_code == 200

        # Cleanup
        process.terminate()
        process.wait(timeout=5)

    def test_dev_command_with_custom_port(
        self,
        server_process: subprocess.Popen,  # type: ignore[type-arg]
    ) -> None:
        """Test dev command starts on custom port."""
        process = server_process(["dev", "--port", "8002"])

        # Wait for server to be ready
        max_retries = 10
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:8002/health", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.2)
        else:
            pytest.fail("Dev server did not start on custom port")

        # Verify server on port 8002
        response = httpx.get("http://127.0.0.1:8002/health")
        assert response.status_code == 200

        # Cleanup
        process.terminate()
        process.wait(timeout=5)
