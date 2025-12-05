"""Integration tests for end-to-end provider detection flow.

Tests the complete workflow without hardcoding provider data:
1. providers.yaml loads successfully
2. Email → detect_provider → ProviderConfig (behavior, not specific values)
3. Error handling works end-to-end
4. All providers in YAML are detectable
"""

import pytest
from mailreactor.core.provider_detector import detect_provider, load_providers
from mailreactor.models.account import ProviderConfig


class TestProviderDetectionFlow:
    """Integration tests for full provider detection workflow."""

    def test_providers_yaml_loads_successfully(self):
        """Verify providers.yaml loads without errors."""
        providers = load_providers()

        assert providers is not None
        assert isinstance(providers, dict)
        assert len(providers) > 0

    def test_detection_returns_config_matching_yaml(self, loaded_providers):
        """Test full flow: email → detect_provider → config matches YAML."""
        # Pick any provider from YAML
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        email = f"user@{any_domain}"

        config = detect_provider(email)

        # Verify behavior: detection succeeded
        assert config is not None
        assert isinstance(config, ProviderConfig)

        # Verify result matches YAML data (not hardcoded expectations)
        expected = loaded_providers[any_provider_key]
        assert config.provider_name == any_provider_key
        assert config.imap_host == expected["imap"]["host"]
        assert config.imap_port == expected["imap"]["port"]
        assert config.imap_ssl == expected["imap"]["ssl"]
        assert config.smtp_host == expected["smtp"]["host"]
        assert config.smtp_port == expected["smtp"]["port"]
        assert config.smtp_starttls == expected["smtp"]["starttls"]

    def test_unknown_domain_returns_none(self):
        """Test unknown domain returns None gracefully (no exception)."""
        config = detect_provider("user@unknown-domain-98765.com")

        assert config is None

    def test_invalid_email_raises_error(self):
        """Test invalid email format raises ValueError end-to-end."""
        with pytest.raises(ValueError, match="Invalid email format"):
            detect_provider("notanemail")

    def test_all_providers_in_yaml_are_detectable(self, loaded_providers):
        """Verify every provider in YAML can be detected."""
        for provider_key, provider_data in loaded_providers.items():
            # Test first domain for each provider
            test_domain = provider_data["domains"][0]
            email = f"user@{test_domain}"

            config = detect_provider(email)

            assert config is not None, f"Failed to detect {provider_key} with domain {test_domain}"
            assert config.provider_name == provider_key
            assert config.imap_host == provider_data["imap"]["host"]
            assert config.smtp_host == provider_data["smtp"]["host"]

    def test_all_aliases_work(self, loaded_providers):
        """Verify all domain aliases in YAML resolve correctly."""
        for provider_key, provider_data in loaded_providers.items():
            for domain in provider_data["domains"]:
                email = f"user@{domain}"

                config = detect_provider(email)

                assert config is not None, f"Alias {domain} for {provider_key} failed"
                assert config.provider_name == provider_key

    def test_case_insensitivity_end_to_end(self, loaded_providers):
        """Test case-insensitive detection in full flow."""
        # Use any provider
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]

        # Test uppercase email
        uppercase_email = f"User@{any_domain.upper()}"
        config = detect_provider(uppercase_email)

        assert config is not None
        assert config.provider_name == any_provider_key
