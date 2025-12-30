"""Unit tests for ServerPlugin protocol.

Tests verify that the ServerPlugin protocol is correctly defined
and can be implemented by plugin classes.

AC #1: ServerPlugin Protocol Created
"""

import inspect

from mailreactor.core.plugin import ServerPlugin


def test_server_plugin_protocol_exists():
    """Test ServerPlugin protocol is defined."""
    assert ServerPlugin is not None


def test_server_plugin_has_name_property():
    """Test ServerPlugin protocol includes name property."""
    # Check protocol has name as property
    assert hasattr(ServerPlugin, "name")


def test_server_plugin_has_required_methods():
    """Test ServerPlugin protocol includes all required methods."""
    required_methods = ["add_cli_options", "register_cli", "start", "stop"]

    for method in required_methods:
        assert hasattr(ServerPlugin, method), f"ServerPlugin missing {method} method"


def test_server_plugin_method_signatures():
    """Test ServerPlugin methods have correct signatures."""
    # Get protocol methods
    protocol_methods = inspect.getmembers(ServerPlugin, predicate=inspect.isfunction)
    method_dict = dict(protocol_methods)

    # Verify add_cli_options signature
    if "add_cli_options" in method_dict:
        sig = inspect.signature(method_dict["add_cli_options"])
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "func" in params

    # Verify register_cli signature
    if "register_cli" in method_dict:
        sig = inspect.signature(method_dict["register_cli"])
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "app" in params

    # Verify start signature
    if "start" in method_dict:
        sig = inspect.signature(method_dict["start"])
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "manager" in params
        assert "config" in params

    # Verify stop signature
    if "stop" in method_dict:
        sig = inspect.signature(method_dict["stop"])
        params = list(sig.parameters.keys())
        assert "self" in params


def test_server_plugin_is_protocol():
    """Test ServerPlugin is a typing.Protocol."""
    # Check if it's a Protocol class
    assert hasattr(ServerPlugin, "_is_protocol")
    assert ServerPlugin._is_protocol is True


class MockPlugin:
    """Mock plugin implementation for testing Protocol compliance."""

    @property
    def name(self) -> str:
        return "mock"

    def add_cli_options(self, func):
        return func

    def register_cli(self, app):
        pass

    async def start(self, manager, config):
        pass

    async def stop(self):
        pass


def test_mock_plugin_implements_protocol():
    """Test a mock plugin can implement the ServerPlugin protocol."""
    plugin = MockPlugin()

    # Verify it has all required attributes
    assert hasattr(plugin, "name")
    assert hasattr(plugin, "add_cli_options")
    assert hasattr(plugin, "register_cli")
    assert hasattr(plugin, "start")
    assert hasattr(plugin, "stop")

    # Verify methods are callable
    assert callable(plugin.add_cli_options)
    assert callable(plugin.register_cli)
    assert callable(plugin.start)
    assert callable(plugin.stop)

    # Verify property works
    assert plugin.name == "mock"
