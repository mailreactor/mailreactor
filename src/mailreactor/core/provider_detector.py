"""Provider auto-detection for IMAP/SMTP settings.

This module provides automatic detection of email provider settings based on
email domain. Detection strategy:

1. Extract domain from email address (user@example.com → example.com)
2. Look up domain in local providers.yaml configuration
3. Handle provider aliases (googlemail.com → gmail, hotmail.com → outlook)
4. Return ProviderConfig with IMAP/SMTP settings, or None if not found

Framework-agnostic: Zero FastAPI dependencies for library mode support.
"""

import yaml  # type: ignore[import-untyped]
import structlog
import httpx
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional

from ..models.account import ProviderConfig

logger = structlog.get_logger(__name__)

# Module-level cache for providers.yaml (loaded once at import)
_PROVIDERS_CACHE: Optional[Dict[str, ProviderConfig]] = None

# Module-level cache for provider domains (loaded once with providers)
_DOMAINS_CACHE: Optional[Dict[str, list[str]]] = None

# Module-level HTTP client for Mozilla/ISP autoconfig queries
_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


def load_providers() -> Dict[str, ProviderConfig]:
    """Load provider configurations from YAML file.

    Reads providers.yaml and parses entries into ProviderConfig Pydantic models.
    Uses module-level cache to avoid repeated file I/O (load once at import).

    Returns:
        Dict mapping provider keys (gmail, outlook, etc.) to ProviderConfig instances

    Raises:
        FileNotFoundError: If providers.yaml not found
        yaml.YAMLError: If YAML parsing fails
    """
    global _PROVIDERS_CACHE, _DOMAINS_CACHE

    if _PROVIDERS_CACHE is not None:
        return _PROVIDERS_CACHE

    # Resolve path: Same directory as provider_detector.py
    providers_path = Path(__file__).parent / "providers.yaml"

    logger.debug("loading_providers", path=str(providers_path))

    with open(providers_path, "r") as f:
        data = yaml.safe_load(f)

    providers = {}
    domains = {}
    for provider_key, config_data in data.items():
        providers[provider_key] = ProviderConfig(
            provider_name=provider_key,
            imap_host=config_data["imap"]["host"],
            imap_port=config_data["imap"]["port"],
            imap_ssl=config_data["imap"]["ssl"],
            smtp_host=config_data["smtp"]["host"],
            smtp_port=config_data["smtp"]["port"],
            smtp_starttls=config_data["smtp"]["starttls"],
        )
        # Cache domains list alongside provider config
        domains[provider_key] = config_data.get("domains", [])

    _PROVIDERS_CACHE = providers
    _DOMAINS_CACHE = domains
    logger.info("providers_loaded", count=len(providers), providers=list(providers.keys()))

    return providers


def extract_domain(email: str) -> str:
    """Extract and normalize domain from email address.

    Args:
        email: Email address (e.g., User@Gmail.COM)

    Returns:
        Lowercase domain (e.g., gmail.com)

    Raises:
        ValueError: If email format is invalid (no @ symbol)
    """
    if "@" not in email:
        raise ValueError(f"Invalid email format: {email}")

    parts = email.split("@")
    if len(parts) != 2:
        raise ValueError(f"Invalid email format (multiple @ symbols): {email}")

    domain = parts[1].lower()

    if not domain:
        raise ValueError(f"Invalid email format (empty domain): {email}")

    return domain


async def detect_provider(email: str) -> Optional[ProviderConfig]:
    """Auto-detect IMAP/SMTP settings for email provider.

    Detection cascade:
    1. Extract domain from email address
    2. Check local providers.yaml (fast path, offline)
    3. If not found, query Mozilla Autoconfig (network call)
    4. If Mozilla fails, query ISP autoconfig (network call)
    5. If all fail, return None (manual configuration required)

    Args:
        email: Email address (e.g., user@gmail.com)

    Returns:
        ProviderConfig with IMAP/SMTP settings if found, None if unknown provider

    Raises:
        ValueError: If email format is invalid

    Example:
        >>> config = await detect_provider("user@gmail.com")
        >>> config.imap_host
        'imap.gmail.com'
        >>> config.smtp_host
        'smtp.gmail.com'

    Note:
        Breaking change from Story 2.1: Now async due to Mozilla/ISP network calls.
        Callers must use await.
    """
    domain = extract_domain(email)

    logger.info("detecting_provider", email=email, domain=domain)

    # Step 1: Load local providers (cached after first call)
    providers = load_providers()

    # Step 2: Check each provider's domain list (fast path, <1ms)
    for provider_key, provider_config in providers.items():
        # Build list of domains from YAML "domains" field
        provider_domains = _get_provider_domains(provider_key)

        if domain in provider_domains:
            logger.info(
                "provider_detected",
                domain=domain,
                provider=provider_key,
                imap_host=provider_config.imap_host,
                smtp_host=provider_config.smtp_host,
                source="local",
            )
            return provider_config

    # Step 3: Unknown in local config - try Mozilla Autoconfig fallback
    logger.info("provider_unknown_locally", domain=domain, action="trying_mozilla_autoconfig")

    mozilla_config = await detect_via_mozilla_autoconfig(domain)
    if mozilla_config:
        return mozilla_config

    # Step 4: All detection methods failed
    logger.info(
        "provider_detection_failed",
        domain=domain,
        message="No provider found via local/Mozilla/ISP",
    )
    return None


def _get_provider_domains(provider_key: str) -> list[str]:
    """Get list of domains for a provider from cached data.

    Retrieves domains from _DOMAINS_CACHE (loaded with providers.yaml).
    No file I/O - uses cached data loaded by load_providers().

    Args:
        provider_key: Provider identifier (gmail, outlook, etc.)

    Returns:
        List of domains for this provider (e.g., ["gmail.com", "googlemail.com"])
    """
    global _DOMAINS_CACHE

    # Ensure providers loaded (will populate _DOMAINS_CACHE)
    if _DOMAINS_CACHE is None:
        load_providers()

    # Type narrowing for mypy
    if _DOMAINS_CACHE is None:
        return []

    return _DOMAINS_CACHE.get(provider_key, [])


def _get_httpx_client() -> httpx.AsyncClient:
    """Get or create module-level httpx client for Mozilla/ISP autoconfig queries.

    Returns:
        Configured AsyncClient with timeout and User-Agent header
    """
    global _HTTP_CLIENT

    if _HTTP_CLIENT is None:
        # 5-second timeout per NFR-P2 (don't block init wizard)
        _HTTP_CLIENT = httpx.AsyncClient(
            timeout=5.0,
            headers={"User-Agent": "MailReactor/0.1.0"},
        )

    return _HTTP_CLIENT


def _parse_autoconfig_xml(xml_content: str) -> Optional[ProviderConfig]:
    """Parse Mozilla Autoconfig XML response into ProviderConfig.

    Args:
        xml_content: XML string from Mozilla/ISP autoconfig

    Returns:
        ProviderConfig if valid XML with required fields, None otherwise

    Example XML:
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
    try:
        root = ET.fromstring(xml_content)

        # Extract IMAP settings (incomingServer[@type='imap'])
        imap_server = root.find(".//incomingServer[@type='imap']")
        if imap_server is None:
            logger.debug("autoconfig_parse_failed", reason="no_imap_server")
            return None

        imap_host = imap_server.findtext("hostname")
        imap_port_str = imap_server.findtext("port")
        imap_socket = imap_server.findtext("socketType", default="SSL")

        if not imap_host or not imap_port_str:
            logger.debug("autoconfig_parse_failed", reason="missing_imap_fields")
            return None

        # Extract SMTP settings (outgoingServer[@type='smtp'])
        smtp_server = root.find(".//outgoingServer[@type='smtp']")
        if smtp_server is None:
            logger.debug("autoconfig_parse_failed", reason="no_smtp_server")
            return None

        smtp_host = smtp_server.findtext("hostname")
        smtp_port_str = smtp_server.findtext("port")
        smtp_socket = smtp_server.findtext("socketType", default="STARTTLS")

        if not smtp_host or not smtp_port_str:
            logger.debug("autoconfig_parse_failed", reason="missing_smtp_fields")
            return None

        # Extract provider name (emailProvider[@id])
        email_provider = root.find(".//emailProvider")
        provider_name = email_provider.get("id") if email_provider is not None else None
        if not provider_name:
            provider_name = "unknown"

        # Build ProviderConfig
        config = ProviderConfig(
            provider_name=provider_name,
            imap_host=imap_host,
            imap_port=int(imap_port_str),
            imap_ssl=(imap_socket.upper() == "SSL"),
            smtp_host=smtp_host,
            smtp_port=int(smtp_port_str),
            smtp_starttls=(smtp_socket.upper() == "STARTTLS"),
        )

        logger.debug("autoconfig_parse_success", imap_host=imap_host, smtp_host=smtp_host)
        return config

    except ET.ParseError as e:
        logger.debug("autoconfig_parse_error", error=str(e), reason="malformed_xml")
        return None
    except (ValueError, AttributeError) as e:
        logger.debug("autoconfig_parse_error", error=str(e), reason="invalid_data")
        return None


async def detect_via_mozilla_autoconfig(domain: str) -> Optional[ProviderConfig]:
    """Query Mozilla Autoconfig database for provider settings (no caching, fresh lookup).

    Detection cascade:
    1. Try Mozilla Autoconfig (HTTPS): https://autoconfig.thunderbird.net/v1.1/{domain}
    2. If 404 or error, try ISP autoconfig (HTTP): http://autoconfig.{domain}/mail/config-v1.1.xml
    3. If both fail, return None

    Args:
        domain: Email domain (e.g., "example.com")

    Returns:
        ProviderConfig if found via Mozilla or ISP, None if both fail
    """
    # Try Mozilla Autoconfig (HTTPS)
    mozilla_url = f"https://autoconfig.thunderbird.net/v1.1/{domain}"
    logger.info("mozilla_autoconfig_lookup", domain=domain, source="mozilla")

    try:
        client = _get_httpx_client()
        response = await client.get(mozilla_url)
        if response.status_code == 200:
            config = _parse_autoconfig_xml(response.text)
            if config:
                logger.info(
                    "mozilla_autoconfig_success",
                    domain=domain,
                    imap_host=config.imap_host,
                    source="mozilla",
                )
                return config
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.debug("mozilla_autoconfig_error", domain=domain, error=str(e), source="mozilla")

    # Try ISP fallback (HTTP - per Mozilla spec)
    isp_url = f"http://autoconfig.{domain}/mail/config-v1.1.xml"
    logger.info("mozilla_autoconfig_lookup", domain=domain, source="isp")

    try:
        client = _get_httpx_client()
        response = await client.get(isp_url)
        if response.status_code == 200:
            config = _parse_autoconfig_xml(response.text)
            if config:
                logger.info(
                    "mozilla_autoconfig_success",
                    domain=domain,
                    imap_host=config.imap_host,
                    source="isp",
                )
                return config
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.debug("mozilla_autoconfig_error", domain=domain, error=str(e), source="isp")

    # All sources failed
    logger.info("mozilla_autoconfig_failed", domain=domain)
    return None


def get_app_password_hint(domain: str) -> Optional[str]:
    """Get provider-specific App Password setup guidance for Gmail, Outlook, Yahoo, iCloud.

    Used by connection validator (Story 2.5) to provide helpful error messages
    when authentication fails for major providers.

    Args:
        domain: Email domain (e.g., "gmail.com")

    Returns:
        Provider-specific hint with App Password link, or None for unknown domains
    """
    APP_PASSWORD_HINTS = {
        "gmail.com": "Gmail requires App Password. Enable 2FA, then generate: https://myaccount.google.com/apppasswords",
        "googlemail.com": "Gmail requires App Password. Enable 2FA, then generate: https://myaccount.google.com/apppasswords",
        "outlook.com": "Outlook requires App Password. Enable 2FA, then generate: https://account.microsoft.com/security",
        "hotmail.com": "Outlook requires App Password. Enable 2FA, then generate: https://account.microsoft.com/security",
        "live.com": "Outlook requires App Password. Enable 2FA, then generate: https://account.microsoft.com/security",
        "yahoo.com": "Yahoo requires App Password. Enable 2FA, then generate: https://login.yahoo.com/account/security",
        "ymail.com": "Yahoo requires App Password. Enable 2FA, then generate: https://login.yahoo.com/account/security",
        "icloud.com": "iCloud requires App Password. Generate at: https://appleid.apple.com/account/manage",
        "me.com": "iCloud requires App Password. Generate at: https://appleid.apple.com/account/manage",
    }

    return APP_PASSWORD_HINTS.get(domain.lower())
