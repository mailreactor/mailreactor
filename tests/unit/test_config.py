"""Unit tests for Pydantic Settings configuration.

Tests cover:
- Default settings values
- Environment variable overrides
- MAILREACTOR_ prefix
- Settings model validation
"""

from mailreactor.config import Settings


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_host(self):
        """Test default host is localhost (security - FR-036)."""
        settings = Settings()
        assert settings.host == "127.0.0.1"

    def test_default_port(self):
        """Test default port is 8000."""
        settings = Settings()
        assert settings.port == 8000

    def test_default_log_level(self):
        """Test default log level is INFO."""
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_default_api_key_header(self):
        """Test default API key header is X-API-Key."""
        settings = Settings()
        assert settings.api_key_header == "X-API-Key"  # pragma: allowlist secret

    def test_default_cors_disabled(self):
        """Test CORS is disabled by default (security)."""
        settings = Settings()
        assert settings.cors_enabled is False

    def test_default_allowed_origins(self):
        """Test default allowed origins when CORS enabled."""
        settings = Settings()
        assert settings.allowed_origins == ["*"]


class TestEnvironmentVariableOverrides:
    """Test environment variable overrides with MAILREACTOR_ prefix."""

    def test_env_override_host(self, monkeypatch):
        """Test MAILREACTOR_HOST overrides default host."""
        monkeypatch.setenv("MAILREACTOR_HOST", "0.0.0.0")
        settings = Settings()
        assert settings.host == "0.0.0.0"

    def test_env_override_port(self, monkeypatch):
        """Test MAILREACTOR_PORT overrides default port."""
        monkeypatch.setenv("MAILREACTOR_PORT", "3000")
        settings = Settings()
        assert settings.port == 3000

    def test_env_override_log_level(self, monkeypatch):
        """Test MAILREACTOR_LOG_LEVEL overrides default log level."""
        monkeypatch.setenv("MAILREACTOR_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.log_level == "DEBUG"

    def test_env_override_api_key_header(self, monkeypatch):
        """Test MAILREACTOR_API_KEY_HEADER overrides default."""
        monkeypatch.setenv("MAILREACTOR_API_KEY_HEADER", "Authorization")
        settings = Settings()
        assert settings.api_key_header == "Authorization"  # pragma: allowlist secret

    def test_env_override_cors_enabled(self, monkeypatch):
        """Test MAILREACTOR_CORS_ENABLED enables CORS."""
        monkeypatch.setenv("MAILREACTOR_CORS_ENABLED", "true")
        settings = Settings()
        assert settings.cors_enabled is True

    def test_env_override_allowed_origins(self, monkeypatch):
        """Test MAILREACTOR_ALLOWED_ORIGINS overrides allowed origins."""
        monkeypatch.setenv("MAILREACTOR_ALLOWED_ORIGINS", '["https://example.com"]')
        settings = Settings()
        assert settings.allowed_origins == ["https://example.com"]
