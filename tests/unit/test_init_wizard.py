"""Unit tests for mailreactor init wizard (Story 2.4).

Tests wizard logic with mocked user input and dependencies.
Focus on behavior we added, not Python/Typer/Pydantic machinery.
"""

from unittest.mock import patch
from typer.testing import CliRunner

from mailreactor.__main__ import app

runner = CliRunner()


def test_existing_config_file_exits_immediately(tmp_path, monkeypatch):
    """AC Flow 1: User runs mailreactor init when config already exists."""
    # Create existing config file
    config_path = tmp_path / "mailreactor.yaml"
    config_path.write_text("email: existing@example.com\n")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Run init command
    result = runner.invoke(app, ["init"])

    # Verify exit code 1 and error message
    assert result.exit_code == 1
    assert "mailreactor.yaml already exists" in result.stdout


def test_invalid_email_format_exits_with_error(tmp_path, monkeypatch):
    """AC Flow 2: User enters invalid email."""
    monkeypatch.chdir(tmp_path)

    # Mock user input: invalid email
    result = runner.invoke(app, ["init"], input="notanemail\n")

    # Verify exit code 1 and error message
    assert result.exit_code == 1
    assert "Invalid email format" in result.stdout


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_happy_path_gmail_auto_detection(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC Flow 3: Gmail user with successful auto-detection and validation."""
    monkeypatch.chdir(tmp_path)

    # Mock provider detection (Gmail)
    from mailreactor.models.account import ProviderConfig

    mock_detect.return_value = ProviderConfig(
        provider_name="Gmail",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_starttls=True,
    )

    # Mock password input
    mock_getpass.return_value = "test-password"

    # Mock connection validation (both succeed)
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init command with valid email
    result = runner.invoke(app, ["init"], input="user@gmail.com\n")

    # Verify success
    assert result.exit_code == 0
    assert "Found settings for Gmail" in result.stdout
    assert "✓ IMAP connection successful" in result.stdout
    assert "✓ SMTP connection successful" in result.stdout
    assert "Configuration saved to mailreactor.yaml" in result.stdout

    # Verify YAML created
    config_path = tmp_path / "mailreactor.yaml"
    assert config_path.exists()

    # Verify file permissions (POSIX only)
    import os

    if os.name != "nt":  # Skip on Windows
        assert config_path.stat().st_mode & 0o777 == 0o600


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_unknown_domain_manual_configuration(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC Flow 5: Unknown domain with manual configuration."""
    monkeypatch.chdir(tmp_path)

    # Mock provider detection (none found)
    mock_detect.return_value = None

    # Mock password inputs (3 prompts: initial, IMAP, SMTP)
    mock_getpass.side_effect = ["initial-password", "imap-password", "smtp-password"]

    # Mock connection validation (both succeed)
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init command with manual prompts
    user_input = (
        "user@unknowndomain.com\n"  # Email
        "imap.unknowndomain.com\n"  # IMAP server
        "993\n"  # IMAP port
        "Y\n"  # IMAP SSL
        "user@unknowndomain.com\n"  # IMAP username
        "smtp.unknowndomain.com\n"  # SMTP server
        "587\n"  # SMTP port
        "Y\n"  # SMTP STARTTLS
        "user@unknowndomain.com\n"  # SMTP username
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0
    assert "Unable to detect mail server settings" in result.stdout
    assert "✓ IMAP connection successful" in result.stdout
    assert "✓ SMTP connection successful" in result.stdout
    assert "Configuration saved to mailreactor.yaml" in result.stdout


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_imap_authentication_failure_with_hint(
    mock_getpass,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC Flow 6: Gmail auth failure shows App Password hint."""
    monkeypatch.chdir(tmp_path)

    # Mock Gmail detection
    from mailreactor.models.account import ProviderConfig

    mock_detect.return_value = ProviderConfig(
        provider_name="Gmail",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_starttls=True,
    )

    # Mock password
    mock_getpass.return_value = "wrong-password"

    # Mock IMAP auth failure
    mock_imap_validate.return_value = (False, "IMAP authentication failed for user@gmail.com")

    # Run init command
    result = runner.invoke(app, ["init"], input="user@gmail.com\n")

    # Verify failure with hint
    assert result.exit_code == 1
    assert "IMAP authentication failed" in result.stdout
    assert "Gmail requires App Password" in result.stdout
    assert "https://myaccount.google.com/apppasswords" in result.stdout


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_imap_connection_timeout(
    mock_getpass,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC Flow 8: IMAP connection timeout."""
    monkeypatch.chdir(tmp_path)

    # Mock detection
    from mailreactor.models.account import ProviderConfig

    mock_detect.return_value = ProviderConfig(
        provider_name="Test",
        imap_host="imap.test.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.test.com",
        smtp_port=587,
        smtp_starttls=True,
    )

    # Mock password
    mock_getpass.return_value = "password"

    # Mock IMAP timeout
    mock_imap_validate.return_value = (False, "Could not connect to imap.test.com:993 (timeout)")

    # Run init command
    result = runner.invoke(app, ["init"], input="user@test.com\n")

    # Verify failure
    assert result.exit_code == 1
    assert "timeout" in result.stdout


def test_ctrl_c_during_password_prompt(tmp_path, monkeypatch):
    """AC Flow 9: User cancels with Ctrl+C."""
    monkeypatch.chdir(tmp_path)

    # Simulate Ctrl+C during password prompt
    with patch("mailreactor.cli.init.getpass.getpass", side_effect=KeyboardInterrupt):
        result = runner.invoke(app, ["init"], input="user@example.com\n")

    # Verify cancelled message
    assert result.exit_code == 1
    assert "Configuration cancelled" in result.stdout


def test_yaml_structure_with_placeholder_passwords(tmp_path, monkeypatch):
    """Verify mailreactor.yaml has correct structure with PLACEHOLDER_PASSWORD."""
    monkeypatch.chdir(tmp_path)

    # Mock all dependencies
    with (
        patch("mailreactor.cli.init.detect_provider") as mock_detect,
        patch("mailreactor.cli.init._validate_imap_connection") as mock_imap,
        patch("mailreactor.cli.init._validate_smtp_connection") as mock_smtp,
        patch("mailreactor.cli.init.getpass.getpass", return_value="test-password"),
    ):
        # Mock Gmail detection
        from mailreactor.models.account import ProviderConfig

        mock_detect.return_value = ProviderConfig(
            provider_name="Gmail",
            imap_host="imap.gmail.com",
            imap_port=993,
            imap_ssl=True,
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_starttls=True,
        )

        # Mock validation success
        mock_imap.return_value = (True, None)
        mock_smtp.return_value = (True, None)

        # Run init
        result = runner.invoke(app, ["init"], input="user@gmail.com\n")
        assert result.exit_code == 0

    # Read YAML and verify structure
    import yaml

    config_path = tmp_path / "mailreactor.yaml"
    with config_path.open("r") as f:
        config = yaml.safe_load(f)

    # Verify structure
    assert config["email"] == "user@gmail.com"
    assert config["imap"]["host"] == "imap.gmail.com"
    assert config["imap"]["port"] == 993
    assert config["imap"]["ssl"] is True
    assert config["imap"]["username"] == "user@gmail.com"
    assert config["imap"]["password"] == "PLACEHOLDER_PASSWORD"  # pragma: allowlist secret
    assert config["smtp"]["host"] == "smtp.gmail.com"
    assert config["smtp"]["port"] == 587
    assert config["smtp"]["starttls"] is True
    assert config["smtp"]["username"] == "user@gmail.com"
    assert config["smtp"]["password"] == "PLACEHOLDER_PASSWORD"  # pragma: allowlist secret
