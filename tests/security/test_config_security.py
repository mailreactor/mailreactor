"""Security tests for YAML config operations.

Verifies security properties:
- Plaintext passwords not in YAML file
- File permissions prevent other users reading
- Master password never stored anywhere
"""

import stat

import pytest

from mailreactor.core.config import save_config
from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig


@pytest.fixture
def sample_account():
    """Sample AccountConfig with sensitive passwords."""
    return AccountConfig(
        email="test@example.com",
        imap=IMAPConfig(
            host="imap.example.com",
            port=993,
            ssl=True,
            username="test@example.com",
            password="secretIMAPpassword123",  # pragma: allowlist secret
        ),
        smtp=SMTPConfig(
            host="smtp.example.com",
            port=587,
            starttls=True,
            username="test@example.com",
            password="secretSMTPpassword456",  # pragma: allowlist secret
        ),
    )


class TestPasswordSecurity:
    """Tests for password encryption security."""

    def test_plaintext_passwords_not_in_yaml_file(self, tmp_path, sample_account):
        """Verify passwords are not visible in file (security test)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        # Read file as text
        yaml_text = config_path.read_text()

        # Verify plaintext passwords are NOT in file
        assert "secretIMAPpassword123" not in yaml_text
        assert "secretSMTPpassword456" not in yaml_text

        # Verify !encrypted tag IS present
        assert "!encrypted" in yaml_text


class TestFilePermissions:
    """Tests for file permission security."""

    def test_file_permissions_prevent_other_users_reading(self, tmp_path, sample_account):
        """Verify file is not readable by other users (AC-6)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        mode = config_path.stat().st_mode

        # Verify no permissions for group or others
        assert not (mode & stat.S_IRGRP), "Group should not have read permission"
        assert not (mode & stat.S_IWGRP), "Group should not have write permission"
        assert not (mode & stat.S_IROTH), "Others should not have read permission"
        assert not (mode & stat.S_IWOTH), "Others should not have write permission"

        # Verify owner has read/write
        assert mode & stat.S_IRUSR, "Owner should have read permission"
        assert mode & stat.S_IWUSR, "Owner should have write permission"


class TestMasterPasswordSecurity:
    """Tests for master password security."""

    def test_master_password_not_stored_anywhere(self, tmp_path, sample_account):
        """Verify master password is NOT stored in filesystem (security test)."""
        config_path = tmp_path / "mailreactor.yaml"
        master_password = "verySecretMasterPassword"  # pragma: allowlist secret

        save_config(config_path, sample_account, master_password)

        # Read file as text
        yaml_text = config_path.read_text()

        # Verify master password is NOT in file
        assert master_password not in yaml_text
        assert "verySecretMasterPassword" not in yaml_text
        assert "MasterPassword" not in yaml_text
        assert "master_password" not in yaml_text
