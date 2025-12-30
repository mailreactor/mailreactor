"""Plugin protocol for Mail Reactor server plugins.

This module defines the ServerPlugin protocol that all Mail Reactor plugins
must implement. Plugins extend the core functionality by adding:
- CLI options (via decorator chaining)
- Subcommands (via Typer app registration)
- Server functionality (via start/stop lifecycle)

Plugin Categories:
- Core plugins (always available): webhooks, cloud, pro_proxy
- Optional plugins (via extras): rest, mcp
- Pro plugins (separate packages): webhooks_advanced, oauth, persistence

See ADR-010 for complete architecture specification.
"""

from typing import Any, Callable, Protocol

import typer


class ServerPlugin(Protocol):
    """Protocol for server plugins.

    Plugins implement this interface to integrate with mailreactor's
    plugin architecture. Core plugins (webhooks, cloud, pro_proxy) are
    always available. Optional plugins (rest, mcp) discovered via try/except.

    Example:
        class RestServerPlugin:
            @property
            def name(self) -> str:
                return "rest"

            def add_cli_options(self, func: Callable) -> Callable:
                # Add REST-specific CLI options
                func = add_cli_option('rest_port', '--rest-port', 'Port', int, 8000)(func)
                return func

            def register_cli(self, app: typer.Typer) -> None:
                # No subcommands for REST plugin
                pass

            async def start(self, manager: object, config: dict) -> None:
                # Start FastAPI server
                ...

            async def stop(self) -> None:
                # Stop FastAPI server
                ...
    """

    @property
    def name(self) -> str:
        """Plugin identifier (e.g., 'webhooks', 'rest', 'mcp').

        Returns:
            Unique plugin name used for discovery and logging
        """
        ...

    def add_cli_options(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Add CLI options to start command via decorator chaining.

        This method wraps the given function with Typer Option decorators
        to add plugin-specific CLI flags. The decorators are applied in
        reverse order (last decorator is outermost), so they appear in
        the correct order in --help output.

        Args:
            func: The function to decorate (typically server.start)

        Returns:
            Decorated function with additional CLI options

        Example:
            def add_cli_options(self, func: Callable) -> Callable:
                func = add_cli_option('rest_port', '--rest-port', 'REST API port', int, 8000)(func)
                func = add_cli_option('rest_host', '--rest-host', 'REST API host', str, '127.0.0.1')(func)
                return func
        """
        ...

    def register_cli(self, app: typer.Typer) -> None:
        """Register subcommands with the CLI app.

        This method allows plugins to add their own subcommand groups
        (e.g., 'mailreactor cloud deploy'). Plugins without subcommands
        can implement this as a no-op.

        Args:
            app: The Typer app instance

        Example:
            def register_cli(self, app: typer.Typer) -> None:
                cloud_app = typer.Typer()
                cloud_app.command("deploy")(self.deploy)
                cloud_app.command("undeploy")(self.undeploy)
                app.add_typer(cloud_app, name="cloud")
        """
        ...

    async def start(self, manager: object, config: dict[str, Any]) -> None:
        """Start the plugin server.

        This method is called when 'mailreactor start' is invoked. The
        plugin should initialize its server (if any) and begin processing.

        Args:
            manager: MailboxManager instance (Story 3-16 - type unknown for now)
            config: Plugin configuration from mailreactor.yaml

        Note:
            The manager type is object for now (Story 3-16 hasn't been implemented).
            Once MailboxManager is created, this will be typed as MailboxManager.
        """
        ...

    async def stop(self) -> None:
        """Stop the plugin server gracefully.

        This method is called during server shutdown. Plugins should clean up
        resources (close connections, stop background tasks, etc.).
        """
        ...
