"""Simplified unit tests for mailreactor init wizard.

Tests our business logic without mocking framework internals.
Covers ACs from Stories 2.4, 2.4.1, 2.5.1, and course correction.
"""

from unittest.mock import patch
from typer.testing import CliRunner

from mailreactor.__main__ import app

runner = CliRunner()


def test_existing_config_file_exits_immediately(tmp_path, monkeypatch):
    """Story 2.4 - Wizard exits if config already exists."""
    config_path = tmp_path / "mailreactor.yaml"
    config_path.write_text("email: existing@example.com\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "mailreactor.yaml already exists" in result.stdout


def test_invalid_email_format_exits_with_error(tmp_path, monkeypatch):
    """Story 2.4 - Invalid email validation."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"], input="notanemail\n")

    assert result.exit_code == 1
    assert "Invalid email format" in result.stdout


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_happy_path_gmail_with_auto_detection(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.4 + 2.5.1 AC-1: Gmail auto-detection with master password."""
    monkeypatch.chdir(tmp_path)

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
    mock_getenv.return_value = None
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = (
        "user@gmail.com\n"  # Email
        "test-password\n"  # Initial password
        "\n\n\n\n"  # IMAP defaults (server, port, ssl, username)
        "\n"  # IMAP password (use initial)
        "\n\n\n\n"  # SMTP defaults (server, port, starttls, username)
        "\n"  # SMTP password (use IMAP)
        "master123\n"  # Master password
        "master123\n"  # Confirm master password
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0, f"stdout:\n{result.stdout}"
    assert "Found settings for Gmail" in result.stdout
    assert "✓ IMAP connection successful" in result.stdout
    assert "✓ SMTP connection successful" in result.stdout
    assert "Choose a master password" in result.stdout
    assert "Configuration saved to mailreactor.yaml" in result.stdout

    # Verify save_config called correctly
    mock_save_config.assert_called_once()
    call_args = mock_save_config.call_args[0]
    assert call_args[1].email == "user@gmail.com"
    assert call_args[2] == "master123"


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_master_password_from_env_var(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.5.1 AC-2: Master password from MAILREACTOR_PASSWORD env var."""
    monkeypatch.chdir(tmp_path)

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
    mock_getenv.return_value = "env-master-password"
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = (
        "user@gmail.com\n"
        "test-password\n"
        "\n\n\n\n\n"  # IMAP defaults
        "\n\n\n\n\n"  # SMTP defaults
        "\n"  # Master password (press Enter to use env var)
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0, f"stdout:\n{result.stdout}"
    assert "Master password [MAILREACTOR_PASSWORD]" in result.stdout
    assert "Configuration saved" in result.stdout

    # Verify env var password used
    mock_save_config.assert_called_once()
    call_args = mock_save_config.call_args[0]
    assert call_args[2] == "env-master-password"


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_master_password_override_env_var(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.5.1 AC-3: User overrides MAILREACTOR_PASSWORD env var."""
    monkeypatch.chdir(tmp_path)

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
    mock_getenv.return_value = "env-master-password"
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = (
        "user@gmail.com\n"
        "test-password\n"
        "\n\n\n\n\n"  # IMAP defaults
        "\n\n\n\n\n"  # SMTP defaults
        "override-password\n"  # Master password (override env var)
        "override-password\n"  # Confirm
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0, f"stdout:\n{result.stdout}"
    assert "Confirm master password" in result.stdout

    # Verify override password used, not env var
    mock_save_config.assert_called_once()
    call_args = mock_save_config.call_args[0]
    assert call_args[2] == "override-password"


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
def test_imap_authentication_failure_exits(
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """Story 2.4 - IMAP auth failure exits wizard."""
    monkeypatch.chdir(tmp_path)

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
    mock_imap_validate.return_value = (False, "IMAP authentication failed for user@gmail.com")

    user_input = (
        "user@gmail.com\n"
        "wrong-password\n"
        "\n\n\n\n\n"  # IMAP defaults
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 1
    assert "IMAP authentication failed" in result.stdout


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_no_validation_flag_skips_connection_tests(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.4 Course Correction AC-1: --no-validation skips IMAP/SMTP tests."""
    monkeypatch.chdir(tmp_path)

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
    mock_getenv.return_value = None

    user_input = (
        "user@gmail.com\n"
        "test-password\n"
        "\n\n\n\n\n"  # IMAP defaults
        "\n\n\n\n\n"  # SMTP defaults
        "master123\n"
        "master123\n"
    )
    result = runner.invoke(app, ["init", "--no-validation"], input=user_input)

    assert result.exit_code == 0, f"stdout:\n{result.stdout}"
    # Validation should NOT be called
    mock_imap_validate.assert_not_called()
    mock_smtp_validate.assert_not_called()
    assert "Configuration saved" in result.stdout


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_no_autoconfig_flag_skips_detection(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.4 Course Correction AC-2: --no-autoconfig skips provider detection."""
    monkeypatch.chdir(tmp_path)

    mock_getenv.return_value = None
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = (
        "user@custom.com\n"
        "test-password\n"
        "imap.custom.com\n"  # Manual IMAP server
        "993\n"
        "Y\n"
        "\n"  # IMAP username default
        "\n"  # IMAP password (use initial)
        "smtp.custom.com\n"  # Manual SMTP server
        "587\n"
        "Y\n"
        "\n"  # SMTP username default
        "\n"  # SMTP password (use IMAP)
        "master123\n"
        "master123\n"
    )
    result = runner.invoke(app, ["init", "--no-autoconfig"], input=user_input)

    assert result.exit_code == 0, f"stdout:\n{result.stdout}"
    # Detection should NOT be called
    mock_detect.assert_not_called()
    assert "Configuration saved" in result.stdout


def test_gmail_shows_proactive_app_password_hint(tmp_path, monkeypatch):
    """Story 2.4.1 AC-1: Gmail shows App Password hint immediately."""
    monkeypatch.chdir(tmp_path)

    with patch("mailreactor.cli.init.detect_provider") as mock_detect:
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

        # Just check hint is shown - don't complete wizard
        result = runner.invoke(app, ["init"], input="user@gmail.com\n")

        # Hint shown after email, before password prompt
        assert "Gmail requires App Password" in result.stdout
        assert "https://myaccount.google.com/apppasswords" in result.stdout


def test_unknown_domain_no_proactive_hint(tmp_path, monkeypatch):
    """Story 2.4.1: Unknown domains don't show proactive hints."""
    monkeypatch.chdir(tmp_path)

    with patch("mailreactor.cli.init.detect_provider") as mock_detect:
        mock_detect.return_value = None

        result = runner.invoke(app, ["init"], input="user@unknown.com\n")

        # No app password hints for unknown domains
        assert "requires App Password" not in result.stdout
        assert "myaccount.google.com" not in result.stdout


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_master_password_mismatch_exits(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.5.1 AC-1: Password mismatch exits without retry."""
    monkeypatch.chdir(tmp_path)

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
    mock_getenv.return_value = None
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = (
        "user@gmail.com\n"
        "test-password\n"
        "\n\n\n\n\n"  # IMAP defaults
        "\n\n\n\n\n"  # SMTP defaults
        "master123\n"  # Master password
        "different\n"  # Confirmation doesn't match
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 1
    assert "Passwords do not match" in result.stdout
    # Config should NOT be saved
    mock_save_config.assert_not_called()


@patch("mailreactor.cli.init.save_config")
@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.os.getenv")
def test_password_cascade_imap_to_smtp(
    mock_getenv,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    mock_save_config,
    tmp_path,
    monkeypatch,
):
    """Story 2.4 Course Correction AC-6: Password cascade initial→IMAP→SMTP."""
    monkeypatch.chdir(tmp_path)

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
    mock_getenv.return_value = None
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    user_input = (
        "user@gmail.com\n"
        "initial-password\n"  # Initial password
        "\n\n\n\n"
        "\n"  # IMAP password: empty (uses initial-password)
        "\n\n\n\n"
        "\n"  # SMTP password: empty (uses IMAP password = initial-password)
        "master123\n"
        "master123\n"
    )
    result = runner.invoke(app, ["init"], input=user_input)

    assert result.exit_code == 0, f"stdout:\n{result.stdout}"

    # Verify both IMAP and SMTP got the initial password (cascade)
    mock_save_config.assert_called_once()
    account_config = mock_save_config.call_args[0][1]
    assert account_config.imap.password == "initial-password"  # pragma: allowlist secret
    assert account_config.smtp.password == "initial-password"  # pragma: allowlist secret
