"""CLI entry point for Mail Reactor.

This module enables invocation via:
    python -m mailreactor start
    python -m mailreactor --help
    python -m mailreactor --version

The console script entry point (mailreactor command) is defined in pyproject.toml.
"""

import typer

# Import server module to register commands
from mailreactor.cli import init, server
from mailreactor.core.plugin_hooks import get_init_hooks
from mailreactor.core.plugin_loader import discover_plugins
from mailreactor.utils.version import get_app_version

# Main CLI app with subcommands
app = typer.Typer(
    name="mailreactor",
    help="Mail Reactor - Headless email client with REST API",
    no_args_is_help=True,
    add_completion=False,  # Disable shell completion install commands
)


def _version_callback(show_version: bool) -> None:
    """Show version and exit if --version flag provided.

    Args:
        show_version: True if --version flag was passed, False otherwise

    Note:
        This is Typer machinery - the callback receives the option's value.
        The is_eager=True flag makes this run before command validation.
    """
    if show_version:
        typer.echo(f"Mail Reactor {get_app_version()}")
        raise typer.Exit()


@app.callback()  # type: ignore[misc]
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Mail Reactor - Headless email client with REST API."""
    pass


# Discover plugins and apply CLI decorators (Story 3-15.5)
# This happens at module load so --help shows plugin options
plugins = discover_plugins(log=False)  # log=False prevents logs during init wizard

# Apply plugin decorators to start command BEFORE registering with app
# Decorator chaining pattern: Each plugin wraps the function with additional CLI options
start_func = server.start
for plugin in plugins.values():
    start_func = plugin.add_cli_options(start_func)

# Apply plugin decorators to dev command as well (same options needed)
dev_func = server.dev
for plugin in plugins.values():
    dev_func = plugin.add_cli_options(dev_func)

# Apply init hook decorators to init command (Story 3-29-5)
# Init hooks add plugin-specific CLI options (e.g., --no-webhook-validation)
init_func = init.init_wizard
for hook in get_init_hooks():
    init_func = hook.add_cli_options(init_func)

# Register commands with decorated functions
app.command("init", help="Interactive wizard for email account setup")(init_func)
app.command("start")(start_func)
app.command("dev", help="Start with auto-reload for development")(dev_func)

# Register plugin subcommands (e.g., cloud deploy)
for plugin in plugins.values():
    plugin.register_cli(app)


@app.command()  # type: ignore[misc]
def accounts() -> None:
    """Manage email accounts (Epic 2 - Not yet implemented)."""
    typer.echo("❌ Account management not yet implemented (Epic 2)", err=True)
    typer.echo("   This will allow adding/removing email accounts", err=True)
    raise typer.Exit(1)


def main() -> None:
    """Entry point for CLI commands.

    This function is called by both:
    - Console script: mailreactor (defined in pyproject.toml)
    - Module invocation: python -m mailreactor
    """
    app()


if __name__ == "__main__":
    main()
