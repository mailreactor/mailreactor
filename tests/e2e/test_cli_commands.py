"""End-to-end tests for CLI command invocation.

Tests both entry point methods:
- Console script: mailreactor start (via pyproject.toml)
- Module invocation: python -m mailreactor start
"""

import subprocess
import sys
import time

import httpx
import pytest


class TestCLIEntryPoints:
    """Test both CLI entry point methods work correctly."""

    def test_module_invocation_starts_server(self) -> None:
        """Test python -m mailreactor start works."""
        # Start server via module invocation
        process = subprocess.Popen(
            [sys.executable, "-m", "mailreactor", "start", "--port", "8002"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for server to start
            max_retries = 10
            server_started = False
            for _ in range(max_retries):
                try:
                    response = httpx.get("http://127.0.0.1:8002/docs", timeout=1.0)
                    if response.status_code == 200:
                        server_started = True
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    time.sleep(0.5)

            assert server_started, "Server did not start via module invocation"

            # Verify docs endpoint
            response = httpx.get("http://127.0.0.1:8002/docs")
            assert response.status_code == 200

        finally:
            # Cleanup
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Console script entry point not tested on Windows in CI"
    )
    def test_console_script_invocation_starts_server(self) -> None:
        """Test mailreactor start console script works (after pip install)."""
        # This test requires the package to be installed (pip install -e .)
        # Skip if not in editable install mode
        try:
            result = subprocess.run(
                ["mailreactor", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                pytest.skip("mailreactor command not available (not installed)")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("mailreactor command not available (not installed)")

        # Start server via console script
        process = subprocess.Popen(
            ["mailreactor", "start", "--port", "8003"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for server to start
            max_retries = 10
            server_started = False
            for _ in range(max_retries):
                try:
                    response = httpx.get("http://127.0.0.1:8003/docs", timeout=1.0)
                    if response.status_code == 200:
                        server_started = True
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    time.sleep(0.5)

            assert server_started, "Server did not start via console script"

            # Verify docs endpoint
            response = httpx.get("http://127.0.0.1:8003/docs")
            assert response.status_code == 200

        finally:
            # Cleanup
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class TestCLIHelpCommand:
    """Test CLI help command displays usage information."""

    def test_module_help_displays_usage(self) -> None:
        """Test python -m mailreactor --help displays usage."""
        result = subprocess.run(
            [sys.executable, "-m", "mailreactor", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "Mail Reactor CLI" in result.stdout or "start" in result.stdout

    def test_start_help_displays_options(self) -> None:
        """Test python -m mailreactor start --help displays options."""
        result = subprocess.run(
            [sys.executable, "-m", "mailreactor", "start", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "--host" in result.stdout
        assert "--port" in result.stdout
        assert "--log-level" in result.stdout
        assert "--json-logs" in result.stdout


class TestCLIErrorHandling:
    """Test CLI error handling for invalid arguments."""

    def test_invalid_port_shows_error(self) -> None:
        """Test invalid port number shows error message."""
        result = subprocess.run(
            [sys.executable, "-m", "mailreactor", "start", "--port", "99999"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should exit with error
        assert result.returncode != 0
        # Should mention invalid value
        assert "Invalid value" in result.stderr or "99999" in result.stderr

    def test_invalid_command_shows_error(self) -> None:
        """Test invalid command shows error message."""
        result = subprocess.run(
            [sys.executable, "-m", "mailreactor", "invalid-command"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should exit with error
        assert result.returncode != 0
        # Should suggest valid commands
        assert "start" in result.stderr or "No such command" in result.stderr
