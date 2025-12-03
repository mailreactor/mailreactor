"""CLI entry point for Mail Reactor.

This module enables invocation via:
    python -m mailreactor start
    python -m mailreactor --help
    python -m mailreactor --version

The console script entry point (mailreactor command) is defined in pyproject.toml.
"""

import typer

# Import server module to register commands
from mailreactor.cli import server
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


# Register commands
app.command("start")(server.start)


@app.command()  # type: ignore[misc]
def dev() -> None:
    """Start development server with auto-reload (Story 1.8 - Not yet implemented)."""
    typer.echo("❌ Dev mode not yet implemented (Story 1.8)", err=True)
    typer.echo("   For now, use: mailreactor start", err=True)
    raise typer.Exit(1)


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
