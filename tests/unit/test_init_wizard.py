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
    """AC Flow 3: Gmail user with successful auto-detection and validation (Story 2.4 course correction).

    Unified flow: Auto-detected values shown as defaults, user presses Enter to accept.
    """
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

    # Mock password inputs (initial, IMAP [REDACTED], SMTP [REDACTED])
    # User presses Enter at IMAP/SMTP password prompts to use defaults
    mock_getpass.side_effect = [
        "test-password",
        "",
        "",
    ]  # Initial, IMAP (use initial), SMTP (use IMAP)

    # Mock connection validation (both succeed)
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init command with unified flow inputs
    # Unified flow prompts (all defaults accepted with Enter):
    user_input = (
        "user@gmail.com\n"  # Email
        # Password via getpass (initial)
        "\n"  # IMAP server [imap.gmail.com] - accept default
        "\n"  # IMAP port [993] - accept default
        "\n"  # IMAP SSL [Y] - accept default
        "\n"  # IMAP username [user@gmail.com] - accept default
        # IMAP password [REDACTED] via getpass - accept default (empty string)
        "\n"  # SMTP server [smtp.gmail.com] - accept default
        "\n"  # SMTP port [587] - accept default
        "\n"  # SMTP STARTTLS [Y] - accept default
        "\n"  # SMTP username [user@gmail.com] - accept default
        # SMTP password [REDACTED] via getpass - accept default (empty string)
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"
    assert "Found settings for Gmail" in result.stdout
    assert "IMAP Configuration:" in result.stdout  # Per-protocol summary (AC-4)
    assert "✓ IMAP connection successful" in result.stdout
    assert "SMTP Configuration:" in result.stdout  # Per-protocol summary (AC-4)
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
def test_imap_authentication_failure_shows_error_only(
    mock_getpass,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC Flow 6: Gmail auth failure shows error (hint shown proactively at start, not on failure)."""
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

    # Mock password (initial, IMAP [REDACTED])
    mock_getpass.side_effect = ["wrong-password", ""]  # Initial, IMAP (use initial)

    # Mock IMAP auth failure
    mock_imap_validate.return_value = (False, "IMAP authentication failed for user@gmail.com")

    # Run init command with unified flow inputs
    user_input = (
        "user@gmail.com\n"  # Email
        # Password via getpass (initial)
        "\n"  # IMAP server [imap.gmail.com] - accept default
        "\n"  # IMAP port [993] - accept default
        "\n"  # IMAP SSL [Y] - accept default
        "\n"  # IMAP username [user@gmail.com] - accept default
        # IMAP password [REDACTED] via getpass - accept default (empty = use initial)
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify failure shows error
    assert result.exit_code == 1
    assert "IMAP authentication failed" in result.stdout

    # Verify hint was shown proactively at start (Story 2.4.1)
    assert "💡 Gmail requires App Password" in result.stdout
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
    """AC Flow 8: IMAP connection timeout (Story 2.4 course correction)."""
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

    # Mock password (initial, IMAP [REDACTED])
    mock_getpass.side_effect = ["password", ""]  # Initial, IMAP (use initial)

    # Mock IMAP timeout
    mock_imap_validate.return_value = (False, "Could not connect to imap.test.com:993 (timeout)")

    # Run init command with unified flow inputs
    user_input = (
        "user@test.com\n"  # Email
        # Password via getpass (initial)
        "\n"  # IMAP server [imap.test.com] - accept default
        "\n"  # IMAP port [993] - accept default
        "\n"  # IMAP SSL [Y] - accept default
        "\n"  # IMAP username [user@test.com] - accept default
        # IMAP password [REDACTED] via getpass - accept default (empty = use initial)
    )
    result = runner.invoke(app, ["init"], input=user_input)

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


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_gmail_shows_proactive_app_password_hint(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """Story 2.4.1 AC-1: Gmail email triggers proactive App Password hint."""
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

    # Mock password inputs
    mock_getpass.side_effect = ["test-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init command
    user_input = (
        "user@gmail.com\n"  # Email - should trigger hint before password prompt
        "\n\n\n\n"  # IMAP defaults
        "\n\n\n\n"  # SMTP defaults
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"

    # Verify proactive hint displayed AFTER email entry (AC-1)
    assert "💡 Gmail requires App Password" in result.stdout
    assert "https://myaccount.google.com/apppasswords" in result.stdout

    # Verify hint appears before IMAP prompts (proves it's shown before password)
    hint_index = result.stdout.find("💡 Gmail requires App Password")
    imap_prompt_index = result.stdout.find("IMAP server")
    assert hint_index < imap_prompt_index, "Hint should appear before IMAP prompts"


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_outlook_shows_proactive_app_password_hint(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """Story 2.4.1 AC-2: Outlook email triggers proactive hint."""
    monkeypatch.chdir(tmp_path)

    from mailreactor.models.account import ProviderConfig

    mock_detect.return_value = ProviderConfig(
        provider_name="Outlook",
        imap_host="outlook.office365.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.office365.com",
        smtp_port=587,
        smtp_starttls=True,
    )

    mock_getpass.side_effect = ["test-password", "", ""]
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = "user@outlook.com\n" + "\n" * 8
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0
    assert "💡 Outlook requires App Password" in result.stdout
    assert "https://account.microsoft.com/security" in result.stdout


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_yahoo_shows_proactive_app_password_hint(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """Story 2.4.1 AC-3: Yahoo email triggers proactive hint."""
    monkeypatch.chdir(tmp_path)

    from mailreactor.models.account import ProviderConfig

    mock_detect.return_value = ProviderConfig(
        provider_name="Yahoo",
        imap_host="imap.mail.yahoo.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.mail.yahoo.com",
        smtp_port=587,
        smtp_starttls=True,
    )

    mock_getpass.side_effect = ["test-password", "", ""]
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = "user@yahoo.com\n" + "\n" * 8
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0
    assert "💡 Yahoo requires App Password" in result.stdout
    assert "https://login.yahoo.com/account/security" in result.stdout


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_icloud_shows_proactive_app_password_hint(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """Story 2.4.1 AC-4: iCloud email triggers proactive hint."""
    monkeypatch.chdir(tmp_path)

    from mailreactor.models.account import ProviderConfig

    mock_detect.return_value = ProviderConfig(
        provider_name="iCloud",
        imap_host="imap.mail.me.com",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.mail.me.com",
        smtp_port=587,
        smtp_starttls=True,
    )

    mock_getpass.side_effect = ["test-password", "", ""]
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = "user@icloud.com\n" + "\n" * 8
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0
    assert "💡 iCloud requires App Password" in result.stdout
    assert "https://appleid.apple.com/account/manage" in result.stdout


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_unknown_domain_no_proactive_hint(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """Story 2.4.1 AC-5: Unknown domain shows no proactive hint."""
    monkeypatch.chdir(tmp_path)

    # Mock no provider detection (unknown domain)
    mock_detect.return_value = None

    mock_getpass.side_effect = ["test-password", "test-password", "test-password"]
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Manual config for unknown domain
    user_input = (
        "user@customdomain.com\n"  # Email - unknown domain
        "imap.customdomain.com\n"  # IMAP server
        "993\n"  # IMAP port
        "Y\n"  # IMAP SSL
        "user@customdomain.com\n"  # IMAP username
        "smtp.customdomain.com\n"  # SMTP server
        "587\n"  # SMTP port
        "Y\n"  # SMTP STARTTLS
        "user@customdomain.com\n"  # SMTP username
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0

    # Verify NO hint displayed (AC-5)
    assert "💡" not in result.stdout  # No emoji hint
    assert "App Password" not in result.stdout  # No hint text
    assert "Unable to detect mail server settings" in result.stdout  # Detection failed message


def test_yaml_structure_with_placeholder_passwords(tmp_path, monkeypatch):
    """Verify mailreactor.yaml has correct structure with PLACEHOLDER_PASSWORD (Story 2.4 course correction)."""
    monkeypatch.chdir(tmp_path)

    # Mock all dependencies
    with (
        patch("mailreactor.cli.init.detect_provider") as mock_detect,
        patch("mailreactor.cli.init._validate_imap_connection") as mock_imap,
        patch("mailreactor.cli.init._validate_smtp_connection") as mock_smtp,
        patch("mailreactor.cli.init.getpass.getpass") as mock_getpass,
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

        # Mock passwords (initial, IMAP [REDACTED], SMTP [REDACTED])
        mock_getpass.side_effect = [
            "test-password",
            "",
            "",
        ]  # Initial, IMAP (use initial), SMTP (use IMAP)

        # Mock validation success
        mock_imap.return_value = (True, None)
        mock_smtp.return_value = (True, None)

        # Run init with unified flow inputs
        user_input = (
            "user@gmail.com\n"  # Email
            # Password via getpass (initial)
            "\n"  # IMAP server [imap.gmail.com] - accept default
            "\n"  # IMAP port [993] - accept default
            "\n"  # IMAP SSL [Y] - accept default
            "\n"  # IMAP username [user@gmail.com] - accept default
            # IMAP password [REDACTED] via getpass - accept default (empty = use initial)
            "\n"  # SMTP server [smtp.gmail.com] - accept default
            "\n"  # SMTP port [587] - accept default
            "\n"  # SMTP STARTTLS [Y] - accept default
            "\n"  # SMTP username [user@gmail.com] - accept default
            # SMTP password [REDACTED] via getpass - accept default (empty = use IMAP)
        )
        result = runner.invoke(app, ["init"], input=user_input)
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
