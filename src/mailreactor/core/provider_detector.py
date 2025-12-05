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
from pathlib import Path
from typing import Dict, Optional

from ..models.account import ProviderConfig

logger = structlog.get_logger(__name__)

# Module-level cache for providers.yaml (loaded once at import)
_PROVIDERS_CACHE: Optional[Dict[str, ProviderConfig]] = None


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
    global _PROVIDERS_CACHE

    if _PROVIDERS_CACHE is not None:
        return _PROVIDERS_CACHE

    # Resolve path: Same directory as provider_detector.py
    providers_path = Path(__file__).parent / "providers.yaml"

    logger.debug("loading_providers", path=str(providers_path))

    with open(providers_path, "r") as f:
        data = yaml.safe_load(f)

    providers = {}
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

    _PROVIDERS_CACHE = providers
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


def detect_provider(email: str) -> Optional[ProviderConfig]:
    """Auto-detect IMAP/SMTP settings for email provider.

    Detection process:
    1. Extract domain from email address
    2. Look up domain in providers.yaml configuration
    3. Check provider aliases (googlemail.com → gmail, etc.)
    4. Return ProviderConfig if found, None if unknown

    Args:
        email: Email address (e.g., user@gmail.com)

    Returns:
        ProviderConfig with IMAP/SMTP settings if found, None if unknown provider

    Raises:
        ValueError: If email format is invalid

    Example:
        >>> config = detect_provider("user@gmail.com")
        >>> config.imap_host
        'imap.gmail.com'
        >>> config.smtp_host
        'smtp.gmail.com'
    """
    domain = extract_domain(email)

    logger.info("detecting_provider", email=email, domain=domain)

    # Load providers (cached after first call)
    providers = load_providers()

    # Check each provider's domain list
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
            )
            return provider_config

    # Unknown provider (not in local configuration)
    logger.info("provider_unknown", domain=domain, message="Domain not found in providers.yaml")
    return None


def _get_provider_domains(provider_key: str) -> list[str]:
    """Get list of domains for a provider from providers.yaml.

    Re-reads providers.yaml to access 'domains' field (not stored in ProviderConfig).
    This is called only during detection, so performance impact is minimal.

    Args:
        provider_key: Provider identifier (gmail, outlook, etc.)

    Returns:
        List of domains for this provider (e.g., ["gmail.com", "googlemail.com"])
    """
    providers_path = Path(__file__).parent / "providers.yaml"

    with open(providers_path, "r") as f:
        data = yaml.safe_load(f)

    # Type narrowing for mypy
    if not isinstance(data, dict):
        return []

    provider_data = data.get(provider_key, {})
    if not isinstance(provider_data, dict):
        return []

    domains = provider_data.get("domains", [])
    return domains if isinstance(domains, list) else []
