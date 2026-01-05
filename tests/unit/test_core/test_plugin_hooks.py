"""Tests for plugin hook registry (Story 3-29-5: AC-1).

Tests the InitHook protocol and hook registry functions:
- Hook registration
- Hook retrieval
- Multiple hooks in order
"""

from rich.console import Console

from mailreactor.core.plugin_hooks import get_init_hooks, register_init_hook


class MockHook1:
    """Mock init hook for testing."""

    def prompt_config(self, console: Console) -> dict:
        return {"hook1": "value1"}


class MockHook2:
    """Mock init hook for testing."""

    def prompt_config(self, console: Console) -> dict:
        return {"hook2": "value2"}


def test_register_and_retrieve_single_hook():
    """Test registering and retrieving a single hook."""
    # Clear any existing hooks first (test isolation)
    from mailreactor.core import plugin_hooks

    plugin_hooks._hooks.clear()

    hook = MockHook1()
    register_init_hook(hook)

    hooks = get_init_hooks()
    assert len(hooks) == 1
    assert hooks[0] is hook


def test_register_and_retrieve_multiple_hooks():
    """Test registering multiple hooks in order."""
    from mailreactor.core import plugin_hooks

    plugin_hooks._hooks.clear()

    hook1 = MockHook1()
    hook2 = MockHook2()

    register_init_hook(hook1)
    register_init_hook(hook2)

    hooks = get_init_hooks()
    assert len(hooks) == 2
    assert hooks[0] is hook1
    assert hooks[1] is hook2


def test_get_init_hooks_returns_copy():
    """Test that get_init_hooks returns a copy (not reference)."""
    from mailreactor.core import plugin_hooks

    plugin_hooks._hooks.clear()

    hook = MockHook1()
    register_init_hook(hook)

    hooks1 = get_init_hooks()
    hooks2 = get_init_hooks()

    # Should be different list objects
    assert hooks1 is not hooks2
    # But contain same hooks
    assert hooks1 == hooks2


def test_hook_execution_order():
    """Test that hooks execute in registration order."""
    from mailreactor.core import plugin_hooks

    plugin_hooks._hooks.clear()

    hook1 = MockHook1()
    hook2 = MockHook2()

    register_init_hook(hook1)
    register_init_hook(hook2)

    console = Console()
    hooks = get_init_hooks()

    # Execute hooks and collect results
    results = [hook.prompt_config(console) for hook in hooks]

    assert results[0] == {"hook1": "value1"}
    assert results[1] == {"hook2": "value2"}
