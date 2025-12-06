"""Integration tests for end-to-end provider detection flow.

Tests the complete workflow without hardcoding provider data:
1. providers.yaml loads successfully
2. Email → detect_provider → ProviderConfig (behavior, not specific values)
3. Mozilla Autoconfig cascade integration (local → Mozilla → ISP → None)
4. Error handling works end-to-end
5. All providers in YAML are detectable
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from mailreactor.core.provider_detector import detect_provider, load_providers
from mailreactor.models.account import ProviderConfig


class TestProviderDetectionFlow:
    """Integration tests for full provider detection workflow (now async)."""

    def test_providers_yaml_loads_successfully(self):
        """Verify providers.yaml loads without errors."""
        providers = load_providers()

        assert providers is not None
        assert isinstance(providers, dict)
        assert len(providers) > 0

    @pytest.mark.asyncio
    async def test_detection_returns_config_matching_yaml(self, loaded_providers):
        """Test full flow: email → detect_provider → config matches YAML."""
        # Pick any provider from YAML
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        email = f"user@{any_domain}"

        config = await detect_provider(email)

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

    @pytest.mark.asyncio
    async def test_unknown_domain_tries_mozilla_cascade(self):
        """Test unknown domain (not in local) triggers Mozilla cascade, returns None if all fail."""
        # Mock Mozilla/ISP to return None (both fail)
        with patch(
            "mailreactor.core.provider_detector.detect_via_mozilla_autoconfig",
            new=AsyncMock(return_value=None),
        ) as mock_mozilla:
            config = await detect_provider("user@unknown-domain-98765.com")

            # Verify Mozilla fallback was called
            mock_mozilla.assert_awaited_once_with("unknown-domain-98765.com")

            # Verify None returned (all sources failed)
            assert config is None

    @pytest.mark.asyncio
    async def test_mozilla_success_returns_detected_config(self):
        """Test Mozilla Autoconfig success after local lookup fails."""
        mozilla_config = ProviderConfig(
            provider_name="mozilla-provider.com",
            imap_host="imap.mozilla-provider.com",
            imap_port=993,
            imap_ssl=True,
            smtp_host="smtp.mozilla-provider.com",
            smtp_port=587,
            smtp_starttls=True,
        )

        with patch(
            "mailreactor.core.provider_detector.detect_via_mozilla_autoconfig",
            new=AsyncMock(return_value=mozilla_config),
        ):
            config = await detect_provider("user@mozilla-provider.com")

            assert config is not None
            assert config.provider_name == "mozilla-provider.com"
            assert config.imap_host == "imap.mozilla-provider.com"
            assert config.smtp_host == "smtp.mozilla-provider.com"

    @pytest.mark.asyncio
    async def test_invalid_email_raises_error(self):
        """Test invalid email format raises ValueError end-to-end."""
        with pytest.raises(ValueError, match="Invalid email format"):
            await detect_provider("notanemail")

    @pytest.mark.asyncio
    async def test_all_providers_in_yaml_are_detectable(self, loaded_providers):
        """Verify every provider in YAML can be detected."""
        for provider_key, provider_data in loaded_providers.items():
            # Test first domain for each provider
            test_domain = provider_data["domains"][0]
            email = f"user@{test_domain}"

            config = await detect_provider(email)

            assert config is not None, f"Failed to detect {provider_key} with domain {test_domain}"
            assert config.provider_name == provider_key
            assert config.imap_host == provider_data["imap"]["host"]
            assert config.smtp_host == provider_data["smtp"]["host"]

    @pytest.mark.asyncio
    async def test_all_aliases_work(self, loaded_providers):
        """Verify all domain aliases in YAML resolve correctly."""
        for provider_key, provider_data in loaded_providers.items():
            for domain in provider_data["domains"]:
                email = f"user@{domain}"

                config = await detect_provider(email)

                assert config is not None, f"Alias {domain} for {provider_key} failed"
                assert config.provider_name == provider_key

    @pytest.mark.asyncio
    async def test_case_insensitivity_end_to_end(self, loaded_providers):
        """Test case-insensitive detection in full flow."""
        # Use any provider
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]

        # Test uppercase email
        uppercase_email = f"User@{any_domain.upper()}"
        config = await detect_provider(uppercase_email)

        assert config is not None
        assert config.provider_name == any_provider_key


class TestMozillaAutoconfigCascadeIntegration:
    """Test full cascade: local → Mozilla → ISP → None (end-to-end)."""

    @pytest.mark.asyncio
    async def test_cascade_local_success_skips_mozilla(self, loaded_providers):
        """Test local match short-circuits (no Mozilla call)."""
        # Use known provider
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        email = f"user@{any_domain}"

        with patch(
            "mailreactor.core.provider_detector.detect_via_mozilla_autoconfig"
        ) as mock_mozilla:
            config = await detect_provider(email)

            # Verify local match succeeded
            assert config is not None
            assert config.provider_name == any_provider_key

            # Verify Mozilla was NOT called (short-circuit)
            mock_mozilla.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cascade_local_fail_mozilla_success(self):
        """Test local fail → Mozilla success."""
        mozilla_xml = """
        <clientConfig>
          <emailProvider id="cascade-test.com">
            <incomingServer type="imap">
              <hostname>imap.cascade-test.com</hostname>
              <port>993</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.cascade-test.com</hostname>
              <port>587</port>
              <socketType>STARTTLS</socketType>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mozilla_xml

        with patch("mailreactor.core.provider_detector._get_httpx_client") as mock_client_getter:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_getter.return_value = mock_client

            config = await detect_provider("user@cascade-test.com")

            # Verify Mozilla config returned
            assert config is not None
            assert config.imap_host == "imap.cascade-test.com"
            assert config.smtp_host == "smtp.cascade-test.com"

    @pytest.mark.asyncio
    async def test_cascade_local_fail_mozilla_fail_isp_success(self):
        """Test local fail → Mozilla fail → ISP success."""
        isp_xml = """
        <clientConfig>
          <emailProvider id="isp-cascade.com">
            <incomingServer type="imap">
              <hostname>imap.isp-cascade.com</hostname>
              <port>993</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.isp-cascade.com</hostname>
              <port>587</port>
              <socketType>STARTTLS</socketType>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        # Mozilla returns 404, ISP returns 200
        mozilla_response = Mock()
        mozilla_response.status_code = 404

        isp_response = Mock()
        isp_response.status_code = 200
        isp_response.text = isp_xml

        with patch("mailreactor.core.provider_detector._get_httpx_client") as mock_client_getter:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [mozilla_response, isp_response]
            mock_client_getter.return_value = mock_client

            config = await detect_provider("user@isp-cascade.com")

            # Verify ISP config returned
            assert config is not None
            assert config.imap_host == "imap.isp-cascade.com"

    @pytest.mark.asyncio
    async def test_cascade_all_fail_returns_none(self):
        """Test local fail → Mozilla fail → ISP fail → None."""
        with patch("mailreactor.core.provider_detector._get_httpx_client") as mock_client_getter:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 404
            mock_client.get.return_value = mock_response
            mock_client_getter.return_value = mock_client

            config = await detect_provider("user@all-fail-cascade.com")

            # Verify None returned (all sources failed)
            assert config is None
