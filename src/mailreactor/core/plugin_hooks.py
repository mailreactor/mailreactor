"""Init hook protocol for plugin configuration during mailreactor init.

This module defines the InitHook protocol that plugins can implement to extend
the init wizard with their own configuration prompts. Hooks are registered
at module import time and executed in order during init wizard flow.

Architecture:
- InitHook protocol: prompt_config(console, **kwargs) -> dict
- InitHook protocol: add_cli_options(func) -> func (usually no-op, uses core flags)
- Registry: register_init_hook() + get_init_hooks()
- Execution: cli/init.py discovers hooks after core config, merges results

Hook Execution Order:
1. Core config (email, password, IMAP, SMTP) - cli/init.py
2. Plugin hooks (webhooks, REST, MCP) - registered via register_init_hook()

Note: Hooks can add their own CLI options via add_cli_options() decorator pattern.
      CLI option values are passed to hooks via **kwargs.

See ADR-010 for plugin architecture specification.
Story 3-29-5: Plugin Init Hook System
"""

from typing import Any, Callable, Protocol

from rich.console import Console


# Global registry for init hooks
_hooks: list["InitHook"] = []


class InitHook(Protocol):
    """Protocol for init wizard hooks.

    Plugins implement this interface to extend the mailreactor init wizard
    with custom configuration prompts. Hooks can add CLI options to the init
    command and display prompts to collect configuration.

    Hooks register at module import time:
        register_init_hook(WebhookInitHook())

    Example:
        class WebhookInitHook:
            def add_cli_options(self, func: Callable) -> Callable:
                # Add --no-webhook-validation flag
                from mailreactor.core.plugin_decorator import add_cli_option
                return add_cli_option('no_webhook_validation', '--no-webhook-validation',
                                     'Skip webhook test', bool, False)(func)

            def prompt_config(self, console: Console, **kwargs: Any) -> dict:
                no_validation = kwargs.get('no_webhook_validation', False)
                url = typer.prompt("Webhook URL for new emails (optional)")
                if url and not no_validation:
                    test_webhook(url)
                return {"webhooks": {"message_received": url}}
    """

    def add_cli_options(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Add CLI options to init command via decorator chaining.

        This method wraps the init_wizard function with Typer Option decorators
        to add plugin-specific CLI flags (e.g., --no-webhook-validation).
        The decorator inserts new parameters before any **kwargs.

        Args:
            func: The init_wizard function to decorate

        Returns:
            Decorated function with additional CLI options

        Example:
            def add_cli_options(self, func: Callable) -> Callable:
                from mailreactor.core.plugin_decorator import add_cli_option
                return add_cli_option('no_webhook_validation', '--no-webhook-validation',
                                     'Skip webhook test', bool, False)(func)
        """
        ...

    def prompt_config(self, console: Console, **kwargs: Any) -> dict[str, Any]:
        """Prompt user for plugin configuration.

        Args:
            console: Rich console for formatted output (spinners, success messages)
            **kwargs: CLI option values (e.g., no_webhook_validation=True)

        Returns:
            Configuration dict to merge into mailreactor.yaml
            Example: {"webhooks": {"message_received": "http://localhost:3000/webhook"}}

        Raises:
            Any exceptions should be caught by cli/init.py (logged and skipped)
        """
        ...


def register_init_hook(hook: InitHook) -> None:
    """Register an init hook to be executed during mailreactor init.

    Hooks are registered at module import time (typically in plugin __init__.py
    or dedicated init_hook.py modules). Hooks execute in registration order.

    Args:
        hook: InitHook implementation to register

    Example:
        # In plugins/webhooks/init_hook.py
        webhook_hook = WebhookInitHook()
        register_init_hook(webhook_hook)
    """
    _hooks.append(hook)


def get_init_hooks() -> list[InitHook]:
    """Retrieve all registered init hooks.

    Returns:
        List of registered hooks in registration order

    Example:
        # In cli/init.py
        hooks = get_init_hooks()
        for hook in hooks:
            config_dict = hook.prompt_config(console)
            config.update(config_dict)
    """
    return _hooks.copy()
