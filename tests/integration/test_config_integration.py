"""Integration tests for YAML config operations.

Tests complete workflows: save → load → decrypt roundtrips.
Verifies the full encryption/config system works end-to-end.
"""

import pytest

from mailreactor.core.config import load_config, save_config
from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig


@pytest.fixture
def sample_account():
    """Sample AccountConfig for integration testing."""
    return AccountConfig(
        email="user@gmail.com",
        imap=IMAPConfig(
            host="imap.gmail.com",
            port=993,
            ssl=True,
            username="user@gmail.com",
            password="imap123Secret",  # pragma: allowlist secret
        ),
        smtp=SMTPConfig(
            host="smtp.gmail.com",
            port=587,
            starttls=True,
            username="user@gmail.com",
            password="smtp456Secret",  # pragma: allowlist secret
        ),
    )


class TestConfigRoundtrip:
    """Integration tests for save → load → decrypt workflows."""

    def test_save_and_load_config_roundtrip(self, tmp_path, sample_account):
        """Full workflow: save → load → decrypt (integration test)."""
        config_path = tmp_path / "mailreactor.yaml"
        master_password = "masterPassword"  # pragma: allowlist secret

        # Save with encryption
        save_config(config_path, sample_account, master_password)

        # Load and decrypt
        yaml_data = load_config(config_path)
        loaded = AccountConfig.from_yaml(yaml_data, master_password)

        # Verify all fields preserved
        assert loaded.email == sample_account.email
        assert loaded.imap.host == sample_account.imap.host
        assert loaded.imap.port == sample_account.imap.port
        assert loaded.imap.ssl == sample_account.imap.ssl
        assert loaded.imap.username == sample_account.imap.username
        assert loaded.imap.password == sample_account.imap.password
        assert loaded.smtp.host == sample_account.smtp.host
        assert loaded.smtp.port == sample_account.smtp.port
        assert loaded.smtp.starttls == sample_account.smtp.starttls
        assert loaded.smtp.username == sample_account.smtp.username
        assert loaded.smtp.password == sample_account.smtp.password

    def test_multiple_passwords_use_different_salts(self, tmp_path, sample_account):
        """Verify IMAP and SMTP passwords have different salts (AC-8 security verification)."""
        config_path = tmp_path / "mailreactor.yaml"

        # Save config
        save_config(config_path, sample_account, "masterPassword")

        # Load and check salts
        yaml_data = load_config(config_path)

        imap_salt = yaml_data["imap"]["password"].salt
        smtp_salt = yaml_data["smtp"]["password"].salt

        # Verify different salts
        assert imap_salt != smtp_salt, "IMAP and SMTP passwords must have unique salts"

        # Verify salt length
        assert len(imap_salt) == 44
        assert len(smtp_salt) == 44
