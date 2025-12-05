"""Unit tests for provider detection module.

Tests cover BEHAVIOR, not configuration data:
- YAML loading and caching
- Domain extraction and validation
- Provider detection logic (matching, not specific providers)
- Error handling

We do NOT test specific provider configurations (Gmail, Outlook, etc.)
Those are data, not code. Changing providers.yaml should not break tests.
"""

import pytest
from mailreactor.core.provider_detector import (
    load_providers,
    extract_domain,
    detect_provider,
)
from mailreactor.models.account import ProviderConfig


class TestLoadProviders:
    """Test provider YAML loading and caching behavior."""

    def test_load_providers_returns_dict_of_provider_configs(self):
        """Verify load_providers returns dict with ProviderConfig values."""
        providers = load_providers()

        assert isinstance(providers, dict)
        assert len(providers) > 0  # At least some providers loaded

        # Verify all values are ProviderConfig instances
        for provider_key, provider_config in providers.items():
            assert isinstance(provider_config, ProviderConfig)
            assert provider_config.provider_name == provider_key
            assert provider_config.imap_host  # Not empty
            assert provider_config.smtp_host  # Not empty
            assert 1 <= provider_config.imap_port <= 65535
            assert 1 <= provider_config.smtp_port <= 65535

    def test_load_providers_caches_result(self):
        """Verify providers loaded once and cached on subsequent calls."""
        import mailreactor.core.provider_detector as module

        original_cache = module._PROVIDERS_CACHE
        module._PROVIDERS_CACHE = None

        try:
            # First call loads from file
            providers1 = load_providers()

            # Second call returns cached result (same object)
            providers2 = load_providers()

            assert providers1 is providers2  # Same object reference
        finally:
            # Restore original cache
            module._PROVIDERS_CACHE = original_cache


class TestExtractDomain:
    """Test domain extraction from email addresses."""

    def test_extract_domain_valid_email(self):
        """Test domain extraction from valid email address."""
        assert extract_domain("user@example.com") == "example.com"
        assert extract_domain("test.user@subdomain.example.com") == "subdomain.example.com"

    def test_extract_domain_case_insensitive(self):
        """Test domain extraction normalizes to lowercase."""
        assert extract_domain("User@Example.COM") == "example.com"
        assert extract_domain("TEST@EXAMPLE.COM") == "example.com"

    def test_extract_domain_invalid_no_at_symbol(self):
        """Test invalid email (no @) raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            extract_domain("notanemail")

    def test_extract_domain_invalid_multiple_at_symbols(self):
        """Test invalid email (multiple @) raises ValueError."""
        with pytest.raises(ValueError, match="multiple @ symbols"):
            extract_domain("user@@example.com")

    def test_extract_domain_invalid_empty_domain(self):
        """Test invalid email (empty domain) raises ValueError."""
        with pytest.raises(ValueError, match="empty domain"):
            extract_domain("user@")


class TestDetectProvider:
    """Test provider detection logic."""

    def test_detect_provider_found_returns_config(self, loaded_providers):
        """Test detection returns ProviderConfig when domain found in YAML."""
        # Use any provider from loaded YAML (don't hardcode which one)
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        email = f"user@{any_domain}"

        config = detect_provider(email)

        assert config is not None
        assert isinstance(config, ProviderConfig)
        assert config.provider_name == any_provider_key
        # Verify returned config matches YAML data
        expected = loaded_providers[any_provider_key]
        assert config.imap_host == expected["imap"]["host"]
        assert config.smtp_host == expected["smtp"]["host"]

    def test_detect_provider_unknown_domain_returns_none(self):
        """Test detection returns None for unknown domain."""
        config = detect_provider("user@unknown-custom-domain-12345.com")

        assert config is None

    def test_detect_provider_case_insensitive(self, loaded_providers):
        """Test detection is case-insensitive for domain matching."""
        # Use any provider domain
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        uppercase_email = f"User@{any_domain.upper()}"

        config = detect_provider(uppercase_email)

        assert config is not None
        assert config.provider_name == any_provider_key

    def test_detect_provider_invalid_email_raises_error(self):
        """Test detection with invalid email format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            detect_provider("notanemail")


class TestProviderAliases:
    """Test provider domain alias handling."""

    def test_provider_aliases_map_to_canonical(self, loaded_providers):
        """Test domain aliases resolve to canonical provider."""
        # Find any provider with multiple domains (aliases)
        provider_with_aliases = None
        for key, data in loaded_providers.items():
            if len(data["domains"]) > 1:
                provider_with_aliases = key
                canonical_domain = data["domains"][0]
                alias_domain = data["domains"][1]
                break

        if not provider_with_aliases:
            pytest.skip("No providers with aliases found in YAML")

        # Test canonical domain
        config1 = detect_provider(f"user@{canonical_domain}")
        assert config1 is not None
        assert config1.provider_name == provider_with_aliases

        # Test alias domain
        config2 = detect_provider(f"user@{alias_domain}")
        assert config2 is not None
        assert config2.provider_name == provider_with_aliases

        # Both should return equivalent config
        assert config1.imap_host == config2.imap_host
        assert config1.smtp_host == config2.smtp_host
