"""Version management utilities.

Centralized version retrieval using importlib.metadata with fallback.
Used by CLI (--version flag) and health endpoint.
"""

from importlib.metadata import PackageNotFoundError, version as get_version


def get_app_version() -> str:
    """Get application version from package metadata.

    Returns:
        Version string (e.g., "0.1.0") or "0.1.0-dev" if package not installed

    Examples:
        >>> version = get_app_version()
        >>> version.startswith("0.")
        True
    """
    try:
        return get_version("mailreactor")
    except (PackageNotFoundError, Exception):
        # Development mode - package not installed or any other error
        return "0.1.0-dev"
