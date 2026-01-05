"""CLI decorator utilities for dynamic Typer option injection.

This module provides helper functions for adding Typer CLI options to functions
via decorator chaining. This enables plugins to dynamically extend the CLI
without modifying core code.

The decorator uses a globals() injection pattern to work around Typer's limitations:
- Typer doesn't support **kwargs (treats it as a positional argument)
- Typer doesn't support typing.Any (RuntimeError)
- Therefore, plugin parameters must be passed via globals() injection

To enable truly discoverable plugins, this module maintains a registry of all
plugin parameters that have been added, allowing core code to query which
parameters exist without hardcoding their names.

See ADR-010 for the complete plugin architecture specification.
"""

import functools
import inspect
from typing import Any, Callable

import typer

# Global registry of plugin parameters added via add_cli_option()
# This enables dynamic discovery without hardcoding parameter names
_PLUGIN_PARAMETERS: list[str] = []


def add_cli_option(
    param_name: str,
    flag: str,
    help_text: str,
    type_: type = str,
    default: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Create a decorator that adds a Typer CLI option to a function.

    This decorator dynamically adds a CLI option parameter to a function's
    signature. It's used by plugins to extend the 'mailreactor init' and
    'mailreactor start' commands with plugin-specific options.

    The parameter is registered in the global _PLUGIN_PARAMETERS list, enabling
    core code to discover which plugin parameters exist without hardcoding names.

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

    # Register parameter in global list for dynamic discovery
    if param_name not in _PLUGIN_PARAMETERS:
        _PLUGIN_PARAMETERS.append(param_name)

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

        # Add new parameter to signature BEFORE **kwargs if it exists
        # Python requires: positional, keyword-only, **kwargs
        var_keyword_idx = None
        for i, p in enumerate(params):
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                var_keyword_idx = i
                break

        if var_keyword_idx is not None:
            # Insert before **kwargs
            params.insert(var_keyword_idx, new_param)
        else:
            # No **kwargs, append at end
            params.append(new_param)

        new_sig = sig.replace(parameters=params)

        # Create wrapper that injects plugin parameters into globals()
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Typer limitation workaround: Since Typer doesn't support **kwargs,
            # we inject plugin parameters into the function's globals() namespace
            # where they can be accessed by core code.
            #
            # The core code uses get_plugin_parameters() to discover which parameters
            # exist, then reads them from globals(). This avoids hardcoding parameter names.
            #
            # Flow:
            # 1. Typer calls wrapper with plugin params in kwargs
            # 2. Wrapper splits kwargs into original vs plugin params
            # 3. Plugin params are injected into func's globals
            # 4. Original function is called with only its original params
            # 5. Original function reads plugin params from globals() using registry

            # Identify which kwargs are plugin-added (not in original signature)
            original_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            plugin_kwargs = {k: v for k, v in kwargs.items() if k not in sig.parameters}

            # Inject plugin parameters into function's global namespace
            func_globals = func.__globals__
            old_values = {}
            try:
                for k, v in plugin_kwargs.items():
                    if k in func_globals:
                        old_values[k] = func_globals[k]
                    func_globals[k] = v

                # Call original function with only its original parameters
                return func(*args, **original_kwargs)
            finally:
                # Clean up: restore original globals
                for k in plugin_kwargs.keys():
                    if k in old_values:
                        func_globals[k] = old_values[k]
                    elif k in func_globals:
                        del func_globals[k]

        # Attach new signature to wrapper
        wrapper.__signature__ = new_sig  # type: ignore[attr-defined]

        return wrapper

    return decorator


def get_plugin_parameters() -> list[str]:
    """Get list of all registered plugin CLI parameters.

    This function enables core code to discover which plugin parameters
    exist without hardcoding their names. Parameters are registered when
    add_cli_option() is called during plugin initialization.

    Returns:
        List of parameter names that have been registered by plugins

    Example:
        # In cli/init.py
        from mailreactor.core.plugin_decorator import get_plugin_parameters

        # Collect all plugin parameters from globals dynamically
        hook_kwargs = {
            param: globals()[param]
            for param in get_plugin_parameters()
            if param in globals()
        }
        hook.prompt_config(console, **hook_kwargs)
    """
    return _PLUGIN_PARAMETERS.copy()
