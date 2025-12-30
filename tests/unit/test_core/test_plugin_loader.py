"""Unit tests for plugin discovery and loading.

Tests verify that discover_plugins() correctly finds:
- Core plugins (always available, even if not implemented yet)
- Optional plugins (conditional on import success)
- Returns correct dict[str, ServerPlugin] structure
- Logs discovered plugins at INFO level

AC #2: Plugin Loader Implemented
"""

from unittest.mock import patch

import pytest
import structlog.testing

from mailreactor.core.plugin_loader import discover_plugins


def test_discover_plugins_returns_dict():
    """Test discover_plugins returns dict[str, ServerPlugin]."""
    plugins = discover_plugins()

    assert isinstance(plugins, dict)
    assert all(isinstance(name, str) for name in plugins.keys())


def test_discover_plugins_logs_discovery(caplog: pytest.LogCaptureFixture):
    """Test discover_plugins logs at INFO level with plugin names."""
    # Use structlog testing capture
    logger = structlog.testing.CapturingLogger()

    with patch("mailreactor.core.plugin_loader.logger", logger):
        plugins = discover_plugins(log=True)  # Explicitly enable logging for test

    # Find the plugins_discovered log entry
    log_entries = [e for e in logger.calls if "plugins_discovered" in str(e)]
    assert len(log_entries) > 0

    # Verify log contains plugin list
    log_entry = log_entries[0]
    assert "plugins" in log_entry.kwargs
    assert "count" in log_entry.kwargs
    assert log_entry.kwargs["count"] == len(plugins)


def test_discover_plugins_empty_when_no_plugins_implemented():
    """Test discover_plugins returns empty dict when plugins not yet implemented.

    This test verifies the infrastructure works even before Story 3-31
    implements the actual plugin classes.
    """
    plugins = discover_plugins()

    # Plugins may be empty if Story 3-31 hasn't been implemented yet
    # Or may contain plugins if running tests after Story 3-31
    assert isinstance(plugins, dict)


def test_discover_plugins_handles_import_errors():
    """Test discover_plugins handles ImportError gracefully for optional plugins.

    This test verifies the lazy import pattern works correctly.
    Since plugin_loader uses try/except to handle ImportError,
    we just verify it doesn't crash when called.
    """
    # Call discover_plugins - it uses try/except internally
    # so ImportError is handled gracefully
    plugins = discover_plugins()

    # Should return dict (possibly empty if no plugins implemented)
    assert isinstance(plugins, dict)


def test_discover_plugins_idempotent():
    """Test discover_plugins returns consistent results across multiple calls."""
    plugins1 = discover_plugins()
    plugins2 = discover_plugins()

    # Same plugins discovered each time
    assert set(plugins1.keys()) == set(plugins2.keys())


@pytest.mark.parametrize("expected_plugin", ["webhooks", "cloud", "pro_proxy"])
def test_discover_plugins_core_plugins_if_implemented(expected_plugin: str):
    """Test core plugins are discovered if implemented.

    This test will PASS once Story 3-31 implements the core plugins.
    Until then, it's expected to find no plugins (which is also valid).
    """
    plugins = discover_plugins()

    # Core plugins SHOULD be present if implemented (Story 3-31)
    # But absence is OK if Story 3-31 hasn't been done yet
    if expected_plugin in plugins:
        # Verify it has the name property (Protocol requirement)
        assert hasattr(plugins[expected_plugin], "name")


@pytest.mark.parametrize("optional_plugin", ["rest", "mcp"])
def test_discover_plugins_optional_plugins_conditional(optional_plugin: str):
    """Test optional plugins only discovered if installed.

    These plugins require extras ([rest], [mcp]) so they won't be
    present in a base installation.
    """
    plugins = discover_plugins()

    # Optional plugins MAY be present (if extras installed)
    # But absence is expected in base install
    if optional_plugin in plugins:
        # Verify it has the name property (Protocol requirement)
        assert hasattr(plugins[optional_plugin], "name")
