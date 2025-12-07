"""Unit tests for provider detection module.

Tests cover BEHAVIOR, not configuration data:
- YAML loading and caching
- Domain extraction and validation
- Provider detection logic (matching, not specific providers)
- Mozilla Autoconfig XML parsing
- Mozilla/ISP autoconfig network lookups (mocked)
- App Password hint generation
- Error handling

We do NOT test specific provider configurations (Gmail, Outlook, etc.)
Those are data, not code. Changing providers.yaml should not break tests.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from mailreactor.core.provider_detector import (
    _parse_autoconfig_xml,
    detect_provider,
    detect_via_mozilla_autoconfig,
    extract_domain,
    get_provider_hint,
    load_providers,
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
    """Test provider detection logic (now async with Mozilla fallback)."""

    @pytest.mark.asyncio
    async def test_detect_provider_found_locally_returns_config(self, loaded_providers):
        """Test detection returns ProviderConfig when domain found in local YAML."""
        # Use any provider from loaded YAML (don't hardcode which one)
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        email = f"user@{any_domain}"

        config = await detect_provider(email)

        assert config is not None
        assert isinstance(config, ProviderConfig)
        assert config.provider_name == any_provider_key
        # Verify returned config matches YAML data
        expected = loaded_providers[any_provider_key]
        assert config.imap_host == expected["imap"]["host"]
        assert config.smtp_host == expected["smtp"]["host"]

    @pytest.mark.asyncio
    async def test_detect_provider_unknown_locally_tries_mozilla(self):
        """Test detection falls back to Mozilla Autoconfig for unknown domains."""
        with patch(
            "mailreactor.core.provider_detector.detect_via_mozilla_autoconfig",
            new=AsyncMock(return_value=None),
        ) as mock_mozilla:
            config = await detect_provider("user@unknown-custom-domain-12345.com")

            # Should call Mozilla fallback
            mock_mozilla.assert_awaited_once_with("unknown-custom-domain-12345.com")
            # Should return None when Mozilla also fails
            assert config is None

    @pytest.mark.asyncio
    async def test_detect_provider_mozilla_success_returns_config(self):
        """Test detection returns Mozilla Autoconfig result when local lookup fails."""
        mozilla_config = ProviderConfig(
            provider_name="mozilla-detected.com",
            imap_host="imap.mozilla-detected.com",
            imap_port=993,
            imap_ssl=True,
            smtp_host="smtp.mozilla-detected.com",
            smtp_port=587,
            smtp_starttls=True,
        )

        with patch(
            "mailreactor.core.provider_detector.detect_via_mozilla_autoconfig",
            new=AsyncMock(return_value=mozilla_config),
        ):
            config = await detect_provider("user@mozilla-detected.com")

            assert config is not None
            assert config.provider_name == "mozilla-detected.com"
            assert config.imap_host == "imap.mozilla-detected.com"

    @pytest.mark.asyncio
    async def test_detect_provider_case_insensitive(self, loaded_providers):
        """Test detection is case-insensitive for domain matching."""
        # Use any provider domain
        any_provider_key = list(loaded_providers.keys())[0]
        any_domain = loaded_providers[any_provider_key]["domains"][0]
        uppercase_email = f"User@{any_domain.upper()}"

        config = await detect_provider(uppercase_email)

        assert config is not None
        assert config.provider_name == any_provider_key

    @pytest.mark.asyncio
    async def test_detect_provider_invalid_email_raises_error(self):
        """Test detection with invalid email format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            await detect_provider("notanemail")


class TestProviderAliases:
    """Test provider domain alias handling."""

    @pytest.mark.asyncio
    async def test_provider_aliases_map_to_canonical(self, loaded_providers):
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
        config1 = await detect_provider(f"user@{canonical_domain}")
        assert config1 is not None
        assert config1.provider_name == provider_with_aliases

        # Test alias domain
        config2 = await detect_provider(f"user@{alias_domain}")
        assert config2 is not None
        assert config2.provider_name == provider_with_aliases

        # Both should return equivalent config
        assert config1.imap_host == config2.imap_host
        assert config1.smtp_host == config2.smtp_host


class TestParseAutoconfigXML:
    """Test Mozilla Autoconfig XML parsing behavior."""

    def test_parse_valid_xml_returns_provider_config(self):
        """Test parsing valid Mozilla Autoconfig XML."""
        xml = """
        <clientConfig>
          <emailProvider id="example.com">
            <incomingServer type="imap">
              <hostname>imap.example.com</hostname>
              <port>993</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.example.com</hostname>
              <port>587</port>
              <socketType>STARTTLS</socketType>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        config = _parse_autoconfig_xml(xml)

        assert config is not None
        assert config.provider_name == "example.com"
        assert config.imap_host == "imap.example.com"
        assert config.imap_port == 993
        assert config.imap_ssl is True
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 587
        assert config.smtp_starttls is True

    def test_parse_xml_missing_imap_returns_none(self):
        """Test parsing XML without IMAP section returns None."""
        xml = """
        <clientConfig>
          <emailProvider id="example.com">
            <outgoingServer type="smtp">
              <hostname>smtp.example.com</hostname>
              <port>587</port>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        config = _parse_autoconfig_xml(xml)

        assert config is None

    def test_parse_xml_missing_smtp_returns_none(self):
        """Test parsing XML without SMTP section returns None."""
        xml = """
        <clientConfig>
          <emailProvider id="example.com">
            <incomingServer type="imap">
              <hostname>imap.example.com</hostname>
              <port>993</port>
            </incomingServer>
          </emailProvider>
        </clientConfig>
        """

        config = _parse_autoconfig_xml(xml)

        assert config is None

    def test_parse_xml_missing_hostname_returns_none(self):
        """Test parsing XML with missing hostname returns None."""
        xml = """
        <clientConfig>
          <emailProvider id="example.com">
            <incomingServer type="imap">
              <port>993</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.example.com</hostname>
              <port>587</port>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        config = _parse_autoconfig_xml(xml)

        assert config is None

    def test_parse_malformed_xml_returns_none(self):
        """Test parsing malformed XML returns None without crashing."""
        xml = "<not-valid-xml"

        config = _parse_autoconfig_xml(xml)

        assert config is None

    def test_parse_xml_invalid_port_returns_none(self):
        """Test parsing XML with invalid port number returns None."""
        xml = """
        <clientConfig>
          <emailProvider id="example.com">
            <incomingServer type="imap">
              <hostname>imap.example.com</hostname>
              <port>not-a-number</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.example.com</hostname>
              <port>587</port>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        config = _parse_autoconfig_xml(xml)

        assert config is None


class TestDetectViaMozillaAutoconfig:
    """Test Mozilla/ISP autoconfig network lookup behavior (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_mozilla_success_returns_config(self):
        """Test Mozilla Autoconfig success returns parsed ProviderConfig."""
        valid_xml = """
        <clientConfig>
          <emailProvider id="test.com">
            <incomingServer type="imap">
              <hostname>imap.test.com</hostname>
              <port>993</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.test.com</hostname>
              <port>587</port>
              <socketType>STARTTLS</socketType>
            </outgoingServer>
          </emailProvider>
        </clientConfig>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = valid_xml

        with patch("mailreactor.core.provider_detector._get_httpx_client") as mock_client_getter:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_getter.return_value = mock_client

            config = await detect_via_mozilla_autoconfig("test.com")

            # Verify HTTP call to Mozilla
            mock_client.get.assert_awaited_once_with(
                "https://autoconfig.thunderbird.net/v1.1/test.com"
            )

            # Verify parsed config
            assert config is not None
            assert config.imap_host == "imap.test.com"
            assert config.smtp_host == "smtp.test.com"

    @pytest.mark.asyncio
    async def test_mozilla_404_tries_isp_fallback(self):
        """Test Mozilla 404 triggers ISP autoconfig fallback."""
        isp_xml = """
        <clientConfig>
          <emailProvider id="isp-detected.com">
            <incomingServer type="imap">
              <hostname>imap.isp-detected.com</hostname>
              <port>993</port>
              <socketType>SSL</socketType>
            </incomingServer>
            <outgoingServer type="smtp">
              <hostname>smtp.isp-detected.com</hostname>
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
            # First call (Mozilla) returns 404, second call (ISP) returns 200
            mock_client.get.side_effect = [mozilla_response, isp_response]
            mock_client_getter.return_value = mock_client

            config = await detect_via_mozilla_autoconfig("isp-detected.com")

            # Verify both URLs called
            assert mock_client.get.await_count == 2
            calls = mock_client.get.await_args_list
            assert calls[0][0][0] == "https://autoconfig.thunderbird.net/v1.1/isp-detected.com"
            assert calls[1][0][0] == "http://autoconfig.isp-detected.com/mail/config-v1.1.xml"

            # Verify ISP config returned
            assert config is not None
            assert config.imap_host == "imap.isp-detected.com"

    @pytest.mark.asyncio
    async def test_both_mozilla_and_isp_fail_returns_none(self):
        """Test both Mozilla and ISP failure returns None."""
        with patch("mailreactor.core.provider_detector._get_httpx_client") as mock_client_getter:
            mock_client = AsyncMock()
            # Both calls return 404
            mock_response = Mock()
            mock_response.status_code = 404
            mock_client.get.return_value = mock_response
            mock_client_getter.return_value = mock_client

            config = await detect_via_mozilla_autoconfig("notfound.com")

            assert config is None

    @pytest.mark.asyncio
    async def test_network_timeout_handled_gracefully(self):
        """Test network timeout doesn't crash, returns None."""
        import httpx

        with patch("mailreactor.core.provider_detector._get_httpx_client") as mock_client_getter:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Connection timeout")
            mock_client_getter.return_value = mock_client

            config = await detect_via_mozilla_autoconfig("timeout-domain.com")

            assert config is None


class TestGetAppPasswordHint:
    """Test App Password hint generation for major providers."""

    def test_gmail_returns_hint_with_link(self):
        """Test Gmail domain returns App Password hint."""
        hint = get_provider_hint("gmail.com")

        assert hint is not None
        assert "Gmail" in hint
        assert "App Password" in hint
        assert "https://myaccount.google.com/apppasswords" in hint

    def test_googlemail_returns_same_hint_as_gmail(self):
        """Test googlemail.com alias returns Gmail hint."""
        hint = get_provider_hint("googlemail.com")

        assert hint is not None
        assert "Gmail" in hint

    def test_outlook_returns_hint_with_link(self):
        """Test Outlook domain returns App Password hint."""
        hint = get_provider_hint("outlook.com")

        assert hint is not None
        assert "Outlook" in hint
        assert "https://account.microsoft.com/security" in hint

    def test_yahoo_returns_hint_with_link(self):
        """Test Yahoo domain returns App Password hint."""
        hint = get_provider_hint("yahoo.com")

        assert hint is not None
        assert "Yahoo" in hint
        assert "https://login.yahoo.com/account/security" in hint

    def test_icloud_returns_hint_with_link(self):
        """Test iCloud domain returns App Password hint."""
        hint = get_provider_hint("icloud.com")

        assert hint is not None
        assert "iCloud" in hint
        assert "https://appleid.apple.com/account/manage" in hint

    def test_unknown_domain_returns_none(self):
        """Test unknown domain returns None."""
        hint = get_provider_hint("custom-domain.com")

        assert hint is None

    def test_case_insensitive_matching(self):
        """Test hint lookup is case-insensitive."""
        hint = get_provider_hint("GMAIL.COM")

        assert hint is not None
        assert "Gmail" in hint
