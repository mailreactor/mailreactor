"""Unit tests for CLI decorator utilities.

Tests verify that add_cli_option() correctly:
- Creates valid Typer Option decorators
- Supports decorator chaining
- Adds parameters to function signatures
- Preserves function metadata (functools.wraps)

AC #3: CLI Decorator Utilities Created
"""

import inspect

import typer

from mailreactor.core.plugin_decorator import add_cli_option


def test_add_cli_option_creates_decorator():
    """Test add_cli_option returns a callable decorator."""
    decorator = add_cli_option("test_param", "--test", "Test option")

    assert callable(decorator)


def test_add_cli_option_adds_parameter_to_signature():
    """Test decorator adds parameter to function signature."""

    def original_func(existing: str = "default"):
        return existing

    # Apply decorator
    decorator = add_cli_option("new_param", "--new-param", "New parameter", str, "new_default")
    decorated_func = decorator(original_func)

    # Check signature includes new parameter
    sig = inspect.signature(decorated_func)
    assert "new_param" in sig.parameters
    assert "existing" in sig.parameters


def test_add_cli_option_preserves_function_metadata():
    """Test decorator preserves original function name and docstring."""

    def original_func():
        """Original docstring."""
        pass

    decorator = add_cli_option("param", "--param", "Parameter")
    decorated_func = decorator(original_func)

    # functools.wraps should preserve these
    assert decorated_func.__name__ == original_func.__name__
    assert decorated_func.__doc__ == original_func.__doc__


def test_add_cli_option_supports_different_types():
    """Test decorator supports int, str, bool types."""

    def func():
        pass

    # Test int type
    int_decorator = add_cli_option("int_param", "--int-param", "Int param", int, 42)
    int_func = int_decorator(func)
    sig_int = inspect.signature(int_func)
    assert sig_int.parameters["int_param"].annotation is int

    # Test str type
    str_decorator = add_cli_option("str_param", "--str-param", "Str param", str, "default")
    str_func = str_decorator(func)
    sig_str = inspect.signature(str_func)
    assert sig_str.parameters["str_param"].annotation is str

    # Test bool type
    bool_decorator = add_cli_option("bool_param", "--bool-param", "Bool param", bool, False)
    bool_func = bool_decorator(func)
    sig_bool = inspect.signature(bool_func)
    assert sig_bool.parameters["bool_param"].annotation is bool


def test_add_cli_option_decorator_chaining():
    """Test multiple decorators can be chained.

    This is the core pattern used by plugins to add multiple CLI options.
    """

    def original_func(base: str = "base"):
        return base

    # Chain multiple decorators
    decorator1 = add_cli_option("param1", "--param1", "First param", str, "default1")
    decorator2 = add_cli_option("param2", "--param2", "Second param", int, 123)
    decorator3 = add_cli_option("param3", "--param3", "Third param", bool, True)

    # Apply in sequence (like plugins do)
    decorated_func = decorator1(original_func)
    decorated_func = decorator2(decorated_func)
    decorated_func = decorator3(decorated_func)

    # Check all parameters present
    sig = inspect.signature(decorated_func)
    assert "base" in sig.parameters
    assert "param1" in sig.parameters
    assert "param2" in sig.parameters
    assert "param3" in sig.parameters


def test_add_cli_option_with_typer_option():
    """Test decorator creates Typer Option annotation."""

    def func():
        pass

    decorator = add_cli_option("param", "--param", "Parameter", str, "default")
    decorated_func = decorator(func)

    sig = inspect.signature(decorated_func)
    param = sig.parameters["param"]

    # Verify Typer Option is used as default
    assert isinstance(param.default, typer.models.OptionInfo)


def test_add_cli_option_flag_format():
    """Test decorator accepts various CLI flag formats."""

    def func():
        pass

    # Test different flag formats
    flags = ["--flag", "--multi-word-flag", "--flag-123"]

    for flag in flags:
        decorator = add_cli_option("param", flag, "Test")
        decorated_func = decorator(func)

        # Should not raise any errors
        assert callable(decorated_func)


def test_add_cli_option_empty_default():
    """Test decorator works with None as default value."""

    def func():
        pass

    decorator = add_cli_option("param", "--param", "Parameter", str, None)
    decorated_func = decorator(func)

    sig = inspect.signature(decorated_func)
    # None default should be preserved
    assert "param" in sig.parameters
