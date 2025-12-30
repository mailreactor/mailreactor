"""Plugin discovery and loading for Mail Reactor.

This module discovers and instantiates available plugins using a lazy import
pattern. Core plugins are always available, while optional plugins are
discovered via try/except to avoid ImportError when not installed.

Plugin Categories:
- Core (always available): webhooks, cloud, pro_proxy
- Optional (via extras): rest, mcp
- Pro (separate packages): discovered by pro_proxy plugin

See ADR-010 for complete architecture specification.
"""

import structlog

from mailreactor.core.plugin import ServerPlugin

logger = structlog.get_logger()


def discover_plugins(log: bool = True) -> dict[str, ServerPlugin]:
    """Discover and instantiate available plugins.

    Discovery cascade:
    1. Core plugins (always available): webhooks, cloud, pro_proxy
    2. Optional plugins (try/except): rest, mcp
    3. Pro plugins (via pro_proxy delegation - Story 3-29.5)

    Args:
        log: If True, log discovered plugins at INFO level (default: True)
             Set to False when called during CLI initialization to prevent
             logs appearing before password prompt or during init wizard

    Returns:
        Dict mapping plugin name to plugin instance

    Example:
        plugins = discover_plugins()  # With logging
        plugins = discover_plugins(log=False)  # Silent discovery

    Note:
        This function MUST NOT raise ImportError. Optional plugins that
        fail to import are silently skipped.
    """
    plugins: dict[str, ServerPlugin] = {}

    # Core plugins - Always available (no try/except needed)
    # NOTE: These imports will fail until Story 3-31 implements the plugins.
    #       For now, we'll use try/except even for core plugins to allow
    #       the infrastructure to be tested before plugin implementations exist.

    # Core Plugin: Webhooks (core protocol)
    try:
        from mailreactor.plugins.webhooks.plugin import WebhooksPlugin

        plugins["webhooks"] = WebhooksPlugin()
    except ImportError:
        # Core plugins not yet implemented (Story 3-31)
        pass

    # Core Plugin: Cloud (deployment)
    try:
        from mailreactor.plugins.cloud.plugin import CloudPlugin

        plugins["cloud"] = CloudPlugin()
    except ImportError:
        # Core plugins not yet implemented (Story 3-31)
        pass

    # Core Plugin: Pro-Proxy (delegation layer)
    try:
        from mailreactor.plugins.pro_proxy.plugin import ProProxyPlugin

        plugins["pro_proxy"] = ProProxyPlugin()
    except ImportError:
        # Core plugins not yet implemented (Story 3-31)
        pass

    # Optional Plugin: REST (FastAPI server)
    try:
        from mailreactor.plugins.rest.plugin import RestPlugin

        plugins["rest"] = RestPlugin()
    except ImportError:
        # REST plugin not installed (requires [rest] extra)
        pass

    # Optional Plugin: MCP (Model Context Protocol)
    try:
        from mailreactor.plugins.mcp.plugin import MCPPlugin

        plugins["mcp"] = MCPPlugin()
    except ImportError:
        # MCP plugin not installed (requires [mcp] extra)
        pass

    # Log discovered plugins at INFO level (if requested)
    if log:
        plugin_names = list(plugins.keys())
        logger.info("plugins_discovered", plugins=plugin_names, count=len(plugin_names))

    return plugins
