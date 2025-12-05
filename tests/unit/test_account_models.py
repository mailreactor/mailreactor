"""Unit tests for account Pydantic models.

Tests cover OUR configuration decisions, not Pydantic's validation machinery:
- Default values we chose (ports, SSL settings, connection status)
- Security configuration (Field(exclude=True) for passwords)
- Auto-generated fields (created_at timestamp factory)
- Design patterns (separate IMAP/SMTP credentials)

We do NOT test:
- Basic model creation (Pydantic always works)
- Field assignment (Pydantic handles this)
- Type validation (Pydantic's responsibility)
"""

from datetime import datetime, timezone
from mailreactor.models.account import (
    ProviderConfig,
    IMAPConfig,
    SMTPConfig,
    MailAccount,
)


class TestModelDefaults:
    """Test our default value choices."""

    def test_provider_config_defaults(self):
        """Test our default port and SSL/STARTTLS choices for auto-detection."""
        config = ProviderConfig(
            provider_name="test",
            imap_host="imap.test.com",
            smtp_host="smtp.test.com",
        )

        # Verify OUR defaults
        assert config.imap_port == 993  # OUR choice: standard IMAP SSL port
        assert config.imap_ssl is True  # OUR choice: use SSL by default
        assert config.smtp_port == 587  # OUR choice: standard SMTP STARTTLS port
        assert config.smtp_starttls is True  # OUR choice: use STARTTLS by default

    def test_imap_config_defaults(self):
        """Test our default IMAP connection settings."""
        config = IMAPConfig(
            host="imap.test.com",
            username="user@test.com",
            password="secret",  # pragma: allowlist secret
        )

        assert config.port == 993  # OUR choice: SSL port default
        assert config.ssl is True  # OUR choice: SSL enabled by default

    def test_smtp_config_defaults(self):
        """Test our default SMTP connection settings."""
        config = SMTPConfig(
            host="smtp.test.com",
            username="user@test.com",
            password="secret",  # pragma: allowlist secret
        )

        assert config.port == 587  # OUR choice: STARTTLS port default
        assert config.starttls is True  # OUR choice: STARTTLS enabled by default

    def test_mail_account_defaults(self):
        """Test our default values for mail account state."""
        account = MailAccount(
            account_id="acc_test123",
            email="user@test.com",
            imap=IMAPConfig(
                host="imap.test.com",
                username="user",
                password="pass",  # pragma: allowlist secret
            ),  # pragma: allowlist secret
            smtp=SMTPConfig(
                host="smtp.test.com",
                username="user",
                password="pass",  # pragma: allowlist secret
            ),  # pragma: allowlist secret
        )

        # Verify OUR defaults
        assert account.connection_status == "pending"  # OUR choice: default state
        assert isinstance(account.created_at, datetime)  # OUR choice: auto-generate timestamp
        assert account.created_at.tzinfo == timezone.utc  # OUR choice: UTC timestamps
        assert (datetime.now(timezone.utc) - account.created_at).total_seconds() < 1  # Recent


class TestSecurityConfiguration:
    """Test our security configuration (Field(exclude=True) for passwords)."""

    def test_password_fields_excluded_from_serialization(self):
        """Test our Field(exclude=True) configuration excludes passwords."""
        imap = IMAPConfig(
            host="imap.test.com",
            username="user@test.com",
            password="imap_secret_password",  # pragma: allowlist secret
        )

        smtp = SMTPConfig(
            host="smtp.test.com",
            username="user@test.com",
            password="smtp_secret_password",  # pragma: allowlist secret
        )

        account = MailAccount(
            account_id="acc_test123",
            email="user@test.com",
            imap=imap,
            smtp=smtp,
        )

        # Test OUR security configuration: passwords excluded from dict
        account_dict = account.model_dump()
        assert "password" not in account_dict.get("imap", {})
        assert "password" not in account_dict.get("smtp", {})

        # Test OUR security configuration: passwords excluded from JSON
        account_json = account.model_dump_json()
        assert "imap_secret_password" not in account_json
        assert "smtp_secret_password" not in account_json
        assert "password" not in account_json


class TestDesignPatterns:
    """Test our architectural design decisions."""

    def test_separate_imap_smtp_credentials(self):
        """Test our design: IMAP and SMTP can have different credentials.

        This supports advanced use cases:
        - Relay services (different SMTP provider)
        - Shared mailboxes (different IMAP credentials)
        - Corporate setups (separate incoming/outgoing servers)
        """
        account = MailAccount(
            account_id="acc_test123",
            email="user@company.com",
            imap=IMAPConfig(
                host="imap.shared.com",
                username="shared@company.com",  # Different IMAP username
                password="imap_pass",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.relay.com",
                username="relay@sendgrid.com",  # Different SMTP username
                password="smtp_pass",  # pragma: allowlist secret
            ),
        )

        # Verify OUR design allows different credentials
        assert account.email == "user@company.com"
        assert account.imap.username == "shared@company.com"
        assert account.smtp.username == "relay@sendgrid.com"
        assert account.imap.host != account.smtp.host
