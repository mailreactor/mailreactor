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

import pytest
from cryptography.fernet import InvalidToken

from mailreactor.core.config import load_config, save_config
from mailreactor.models.account import (
    AccountConfig,
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


class TestAccountConfigFromYAML:
    """Test AccountConfig.from_yaml() classmethod (AC-5)."""

    @pytest.fixture
    def sample_account_config(self):
        """Sample AccountConfig for testing."""
        return AccountConfig(
            email="test@gmail.com",
            imap=IMAPConfig(
                host="imap.gmail.com",
                port=993,
                ssl=True,
                username="test@gmail.com",
                password="originalImapPassword",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.gmail.com",
                port=587,
                starttls=True,
                username="test@gmail.com",
                password="originalSmtpPassword",  # pragma: allowlist secret
            ),
        )

    def test_from_yaml_decrypts_passwords(self, tmp_path, sample_account_config):
        """Verify from_yaml() decrypts passwords correctly (AC-5)."""
        config_path = tmp_path / "mailreactor.yaml"
        master_password = "masterPassword"  # pragma: allowlist secret

        # Save config with encryption
        save_config(config_path, sample_account_config, master_password)

        # Load and decrypt
        yaml_data = load_config(config_path)
        loaded = AccountConfig.from_yaml(yaml_data, master_password)

        # Verify passwords were decrypted correctly
        assert loaded.imap.password == sample_account_config.imap.password
        assert loaded.smtp.password == sample_account_config.smtp.password

    def test_from_yaml_wrong_password_raises_error(self, tmp_path, sample_account_config):
        """Verify wrong master password fails (AC-7)."""
        config_path = tmp_path / "mailreactor.yaml"

        # Save with correct password
        save_config(config_path, sample_account_config, "correctMaster")

        # Try to load with wrong password
        yaml_data = load_config(config_path)

        with pytest.raises(InvalidToken):
            AccountConfig.from_yaml(yaml_data, "wrongMaster")

    def test_from_yaml_creates_valid_account_config(self, tmp_path, sample_account_config):
        """Verify from_yaml() preserves all fields (AC-5)."""
        config_path = tmp_path / "mailreactor.yaml"
        master_password = "masterPassword"  # pragma: allowlist secret

        # Save and load
        save_config(config_path, sample_account_config, master_password)
        yaml_data = load_config(config_path)
        loaded = AccountConfig.from_yaml(yaml_data, master_password)

        # Verify all fields preserved
        assert loaded.email == sample_account_config.email
        assert loaded.imap.host == sample_account_config.imap.host
        assert loaded.imap.port == sample_account_config.imap.port
        assert loaded.imap.ssl == sample_account_config.imap.ssl
        assert loaded.imap.username == sample_account_config.imap.username
        assert loaded.imap.password == sample_account_config.imap.password
        assert loaded.smtp.host == sample_account_config.smtp.host
        assert loaded.smtp.port == sample_account_config.smtp.port
        assert loaded.smtp.starttls == sample_account_config.smtp.starttls
        assert loaded.smtp.username == sample_account_config.smtp.username
        assert loaded.smtp.password == sample_account_config.smtp.password
