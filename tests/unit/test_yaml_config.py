"""Unit tests for YAML config operations (core/config.py).

Tests YAML loading/saving with !encrypted tag support. Does NOT mock
PyYAML - we test OUR config machinery, not YAML parsing itself.

Coverage target: 90%+ (file operations + YAML parsing)
"""

import stat
from pathlib import Path

import pytest

from mailreactor.core.config import EncryptedValue, load_config, save_config
from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig


@pytest.fixture
def sample_account():
    """Sample AccountConfig for testing."""
    return AccountConfig(
        email="test@gmail.com",
        imap=IMAPConfig(
            host="imap.gmail.com",
            port=993,
            ssl=True,
            username="test@gmail.com",
            password="imapPassword123",  # pragma: allowlist secret
        ),
        smtp=SMTPConfig(
            host="smtp.gmail.com",
            port=587,
            starttls=True,
            username="test@gmail.com",
            password="smtpPassword456",  # pragma: allowlist secret
        ),
    )


class TestEncryptedValue:
    """Tests for EncryptedValue class."""

    def test_encrypted_value_splits_salt_and_ciphertext(self):
        """Verify EncryptedValue correctly splits combined string."""
        # Simulate encrypted format: 44-char salt + ciphertext
        salt = "A" * 44
        ciphertext = "B" * 100
        combined = salt + ciphertext

        encrypted = EncryptedValue(combined)

        assert encrypted.salt == salt
        assert encrypted.ciphertext == ciphertext
        assert len(encrypted.salt) == 44

    def test_encrypted_constructor_creates_encrypted_value(self):
        """Verify encrypted_constructor() creates EncryptedValue (AC-10)."""
        import yaml

        yaml_content = "password: !encrypted " + "A" * 44 + "B" * 100

        data = yaml.safe_load(yaml_content)

        assert isinstance(data["password"], EncryptedValue)
        assert len(data["password"].salt) == 44


class TestSaveConfig:
    """Tests for save_config() function."""

    def test_save_config_creates_yaml_file(self, tmp_path, sample_account):
        """Verify save_config creates file (AC-3)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        assert config_path.exists()
        assert config_path.is_file()

    def test_save_config_encrypts_imap_password(self, tmp_path, sample_account):
        """Verify IMAP password is encrypted (AC-3)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        # Read file as text and verify password is not plaintext
        yaml_text = config_path.read_text()
        assert "imapPassword123" not in yaml_text
        assert "!encrypted" in yaml_text

    def test_save_config_encrypts_smtp_password(self, tmp_path, sample_account):
        """Verify SMTP password is encrypted (AC-3)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        # Read file as text and verify password is not plaintext
        yaml_text = config_path.read_text()
        assert "smtpPassword456" not in yaml_text
        assert "!encrypted" in yaml_text

    def test_save_config_sets_file_permissions_0600(self, tmp_path, sample_account):
        """Verify file permissions are 0600 (AC-3, AC-6)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        mode = config_path.stat().st_mode
        assert stat.S_IMODE(mode) == 0o600

    def test_save_config_uses_unique_salts(self, tmp_path, sample_account):
        """Verify IMAP and SMTP passwords have different salts (AC-8)."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        loaded = load_config(config_path)
        imap_salt = loaded["imap"]["password"].salt
        smtp_salt = loaded["smtp"]["password"].salt

        assert imap_salt != smtp_salt, "IMAP and SMTP salts must differ"

    def test_save_config_preserves_all_fields(self, tmp_path, sample_account):
        """Verify all config fields are saved."""
        config_path = tmp_path / "mailreactor.yaml"

        save_config(config_path, sample_account, "masterPassword")

        loaded = load_config(config_path)

        assert loaded["email"] == sample_account.email
        assert loaded["imap"]["host"] == sample_account.imap.host
        assert loaded["imap"]["port"] == sample_account.imap.port
        assert loaded["imap"]["ssl"] == sample_account.imap.ssl
        assert loaded["imap"]["username"] == sample_account.imap.username
        assert loaded["smtp"]["host"] == sample_account.smtp.host
        assert loaded["smtp"]["port"] == sample_account.smtp.port
        assert loaded["smtp"]["starttls"] == sample_account.smtp.starttls
        assert loaded["smtp"]["username"] == sample_account.smtp.username


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_load_config_parses_yaml(self, tmp_path, sample_account):
        """Verify load_config parses YAML structure (AC-4)."""
        config_path = tmp_path / "mailreactor.yaml"
        save_config(config_path, sample_account, "masterPassword")

        loaded = load_config(config_path)

        assert loaded["email"] == "test@gmail.com"
        assert loaded["imap"]["host"] == "imap.gmail.com"
        assert loaded["smtp"]["host"] == "smtp.gmail.com"

    def test_load_config_parses_encrypted_tag(self, tmp_path, sample_account):
        """Verify !encrypted tag creates EncryptedValue (AC-4)."""
        config_path = tmp_path / "mailreactor.yaml"
        save_config(config_path, sample_account, "masterPassword")

        loaded = load_config(config_path)

        assert isinstance(loaded["imap"]["password"], EncryptedValue)
        assert isinstance(loaded["smtp"]["password"], EncryptedValue)

    def test_load_config_missing_file_raises_error(self, tmp_path):
        """Verify missing file raises FileNotFoundError (AC-4)."""
        config_path = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError, match="Configuration not found"):
            load_config(config_path)

    def test_load_config_default_path(self, tmp_path, sample_account, monkeypatch):
        """Verify load_config uses default path ./mailreactor.yaml."""
        # Change working directory to tmp_path
        monkeypatch.chdir(tmp_path)

        # Save to default location
        config_path = Path("mailreactor.yaml")
        save_config(config_path, sample_account, "masterPassword")

        # Load without specifying path
        loaded = load_config()

        assert loaded["email"] == "test@gmail.com"
