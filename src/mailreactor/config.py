"""Application configuration using Pydantic Settings.

This module provides type-safe configuration management with support for:
- Environment variable overrides (MAILREACTOR_ prefix)
- .env file loading
- Sensible defaults favoring security (localhost binding, INFO log level)

All settings can be overridden via environment variables:
    MAILREACTOR_HOST=0.0.0.0 mailreactor start
    MAILREACTOR_PORT=3000 mailreactor start
    MAILREACTOR_LOG_LEVEL=DEBUG mailreactor start

Or via .env file:
    MAILREACTOR_HOST=0.0.0.0
    MAILREACTOR_PORT=3000
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # type: ignore[misc]
    """Application settings with environment variable support.

    All fields can be overridden via environment variables with MAILREACTOR_ prefix.
    For example: MAILREACTOR_HOST=0.0.0.0 will override the default host.

    Attributes:
        host: Server bind address (default: 127.0.0.1 for security)
        port: Server port (default: 8000)
        log_level: Logging level (DEBUG, INFO, WARN, ERROR)
        api_key_header: HTTP header name for API key authentication
        cors_enabled: Enable CORS middleware (disabled by default for security)
        allowed_origins: CORS allowed origins when CORS is enabled

    Examples:
        >>> settings = Settings()
        >>> settings.host
        '127.0.0.1'
        >>>
        >>> # Override via environment variable
        >>> import os
        >>> os.environ['MAILREACTOR_PORT'] = '3000'
        >>> settings = Settings()
        >>> settings.port
        3000
    """

    # Server configuration
    host: str = "127.0.0.1"  # Localhost by default (security - FR-036)
    port: int = 8000
    log_level: str = "INFO"

    # Security configuration
    api_key_header: str = "X-API-Key"

    # CORS configuration (disabled by default for security)
    cors_enabled: bool = False
    allowed_origins: list[str] = ["*"]  # Only used when cors_enabled=True

    model_config = SettingsConfigDict(
        env_prefix="MAILREACTOR_",
        env_file=".env",
        case_sensitive=False,
    )


# Singleton settings instance
settings = Settings()
