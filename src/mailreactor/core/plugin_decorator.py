"""CLI decorator utilities for dynamic Typer option injection.

This module provides helper functions for adding Typer CLI options to functions
via decorator chaining. This enables plugins to dynamically extend the CLI
without modifying core code.

See ADR-010 for the complete plugin architecture specification.
"""

import functools
import inspect
from typing import Any, Callable

import typer


def add_cli_option(
    param_name: str,
    flag: str,
    help_text: str,
    type_: type = str,
    default: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Create a decorator that adds a Typer CLI option to a function.

    This decorator dynamically adds a CLI option parameter to a function's
    signature. It's used by plugins to extend the 'mailreactor start' command
    with plugin-specific options.

    Args:
        param_name: Parameter name in function signature (e.g., 'rest_port')
        flag: CLI flag (e.g., '--rest-port')
        help_text: Help text shown in --help output
        type_: Parameter type (int, str, bool, etc.)
        default: Default value if not provided via CLI

    Returns:
        Decorator function that adds the CLI option

    Example:
        @add_cli_option('rest_port', '--rest-port', 'REST API port', int, 8000)
        def start(rest_port: int = 8000):
            print(f"Starting on port {rest_port}")

    Note:
        When using decorator chaining, decorators are applied in reverse order
        (last decorator is outermost). This means the last add_cli_option call
        will be the first option in --help output.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap function with Typer Option.

        Args:
            func: The function to decorate

        Returns:
            Decorated function with CLI option added
        """
        # Get existing signature
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        # Create new parameter with Typer Option annotation
        new_param = inspect.Parameter(
            param_name,
            inspect.Parameter.KEYWORD_ONLY,
            default=typer.Option(default, flag, help=help_text),
            annotation=type_,
        )

        # Add new parameter to signature
        params.append(new_param)
        new_sig = sig.replace(parameters=params)

        # Create wrapper that accepts the new parameter
        @functools.wraps(func)
        def wrapper(**kwargs: Any) -> Any:
            # Filter out the new parameter and pass remaining kwargs
            func_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return func(**func_kwargs)

        # Attach new signature to wrapper
        wrapper.__signature__ = new_sig  # type: ignore[attr-defined]

        return wrapper

    return decorator
