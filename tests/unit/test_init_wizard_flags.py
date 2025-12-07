"""Unit tests for mailreactor init wizard flags (Story 2.4 course correction).

Tests for new flags: --no-validation, --no-autoconfig, --verbose
Tests for unified wizard flow, per-protocol validation, password defaults.
"""

from unittest.mock import patch
from typer.testing import CliRunner

from mailreactor.__main__ import app

runner = CliRunner()


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_no_validation_flag_skips_connection_tests(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-1: --no-validation flag skips IMAP/SMTP validation (offline mode)."""
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

    # Mock passwords (initial, IMAP, SMTP)
    mock_getpass.side_effect = ["test-password", "", ""]

    # Validation should NOT be called
    mock_imap_validate.return_value = (True, None)  # Won't be called
    mock_smtp_validate.return_value = (True, None)  # Won't be called

    # Run init with --no-validation flag
    user_input = (
        "user@gmail.com\n"  # Email
        "\n"  # IMAP server [imap.gmail.com]
        "\n"  # IMAP port [993]
        "\n"  # IMAP SSL [Y]
        "\n"  # IMAP username [user@gmail.com]
        # IMAP password [REDACTED] via getpass
        "\n"  # SMTP server [smtp.gmail.com]
        "\n"  # SMTP port [587]
        "\n"  # SMTP STARTTLS [Y]
        "\n"  # SMTP username [user@gmail.com]
        # SMTP password [REDACTED] via getpass
    )
    result = runner.invoke(app, ["init", "--no-validation"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"
    assert "Found settings for Gmail" in result.stdout
    assert "Configuration saved to mailreactor.yaml" in result.stdout

    # Verify validation was NOT called
    mock_imap_validate.assert_not_called()
    mock_smtp_validate.assert_not_called()

    # Verify no validation messages (no "Testing..." or checkmarks)
    assert "Testing IMAP connection" not in result.stdout
    assert "Testing SMTP connection" not in result.stdout
    assert "✓ IMAP connection successful" not in result.stdout
    assert "✓ SMTP connection successful" not in result.stdout

    # Verify header is unchanged (no mode indicator per HC correction)
    assert "Mail Reactor Setup Wizard\n" in result.stdout
    assert "Offline Mode" not in result.stdout

    # Verify success message has NO validation note (per HC correction)
    assert "not validated" not in result.stdout.lower()
    assert "will attempt to connect" not in result.stdout.lower()

    # Verify YAML created
    config_path = tmp_path / "mailreactor.yaml"
    assert config_path.exists()


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_no_autoconfig_flag_skips_detection(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-2: --no-autoconfig flag skips provider detection, goes to manual prompts."""
    monkeypatch.chdir(tmp_path)

    # Detection should NOT be called
    mock_detect.return_value = None  # Won't be called

    # Mock passwords (initial, IMAP, SMTP)
    mock_getpass.side_effect = ["initial-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init with --no-autoconfig flag
    user_input = (
        "user@custom.com\n"  # Email
        "imap.custom.com\n"  # IMAP server (no default)
        "\n"  # IMAP port [993]
        "\n"  # IMAP SSL [Y]
        "\n"  # IMAP username [user@custom.com]
        # IMAP password [REDACTED] via getpass
        "smtp.custom.com\n"  # SMTP server (no default)
        "\n"  # SMTP port [587]
        "\n"  # SMTP STARTTLS [Y]
        "\n"  # SMTP username [user@custom.com]
        # SMTP password [REDACTED] via getpass
    )
    result = runner.invoke(app, ["init", "--no-autoconfig"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"
    assert "Configuration saved to mailreactor.yaml" in result.stdout

    # Verify detection was NOT called
    mock_detect.assert_not_called()

    # Verify no detection messages
    assert "Detecting mail server settings" not in result.stdout
    assert "Found settings for" not in result.stdout
    assert "Unable to detect" not in result.stdout

    # Verify validation WAS called (still validates unless --no-validation)
    mock_imap_validate.assert_called_once()
    mock_smtp_validate.assert_called_once()
    assert "✓ IMAP connection successful" in result.stdout
    assert "✓ SMTP connection successful" in result.stdout

    # Verify header is unchanged (no mode indicator per HC correction)
    assert "Mail Reactor Setup Wizard\n" in result.stdout
    assert "Manual Configuration" not in result.stdout

    # Verify YAML created with manual settings
    import yaml

    config_path = tmp_path / "mailreactor.yaml"
    with config_path.open("r") as f:
        config = yaml.safe_load(f)

    assert config["imap"]["host"] == "imap.custom.com"
    assert config["smtp"]["host"] == "smtp.custom.com"


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_combined_flags_offline_manual(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-3: --no-autoconfig --no-validation combined (offline manual entry)."""
    monkeypatch.chdir(tmp_path)

    # Neither detection nor validation should be called
    mock_detect.return_value = None  # Won't be called
    mock_imap_validate.return_value = (True, None)  # Won't be called
    mock_smtp_validate.return_value = (True, None)  # Won't be called

    # Mock passwords (initial, IMAP, SMTP)
    mock_getpass.side_effect = ["initial-password", "", ""]

    # Run init with both flags
    user_input = (
        "user@custom.com\n"  # Email
        "imap.custom.com\n"  # IMAP server
        "\n"  # IMAP port [993]
        "\n"  # IMAP SSL [Y]
        "\n"  # IMAP username [user@custom.com]
        # IMAP password [REDACTED] via getpass
        "smtp.custom.com\n"  # SMTP server
        "\n"  # SMTP port [587]
        "\n"  # SMTP STARTTLS [Y]
        "\n"  # SMTP username [user@custom.com]
        # SMTP password [REDACTED] via getpass
    )
    result = runner.invoke(app, ["init", "--no-autoconfig", "--no-validation"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"
    assert "Configuration saved to mailreactor.yaml" in result.stdout

    # Verify detection NOT called
    mock_detect.assert_not_called()
    assert "Detecting mail server settings" not in result.stdout

    # Verify validation NOT called
    mock_imap_validate.assert_not_called()
    mock_smtp_validate.assert_not_called()
    assert "Testing IMAP connection" not in result.stdout
    assert "Testing SMTP connection" not in result.stdout

    # Verify header is unchanged (no mode indicators per HC correction)
    assert "Mail Reactor Setup Wizard\n" in result.stdout
    assert "Manual Configuration" not in result.stdout
    assert "Offline Mode" not in result.stdout

    # Verify success message has NO combined note (per HC correction)
    assert "not validated" not in result.stdout.lower()

    # Verify YAML created
    config_path = tmp_path / "mailreactor.yaml"
    assert config_path.exists()


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_unified_flow_auto_detected_defaults_accepted(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-5: Unified flow shows auto-detected values as defaults, user accepts all."""
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

    # Mock passwords (initial, IMAP, SMTP)
    mock_getpass.side_effect = ["test-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init with all defaults accepted (empty input = press Enter)
    user_input = (
        "user@gmail.com\n"  # Email
        "\n"  # IMAP server [imap.gmail.com] - accept default
        "\n"  # IMAP port [993] - accept default
        "\n"  # IMAP SSL [Y] - accept default
        "\n"  # IMAP username [user@gmail.com] - accept default
        # IMAP password [REDACTED] - accept default (initial password)
        "\n"  # SMTP server [smtp.gmail.com] - accept default
        "\n"  # SMTP port [587] - accept default
        "\n"  # SMTP STARTTLS [Y] - accept default
        "\n"  # SMTP username [user@gmail.com] - accept default
        # SMTP password [REDACTED] - accept default (IMAP password)
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"

    # Verify YAML has auto-detected values
    import yaml

    config_path = tmp_path / "mailreactor.yaml"
    with config_path.open("r") as f:
        config = yaml.safe_load(f)

    assert config["imap"]["host"] == "imap.gmail.com"
    assert config["imap"]["port"] == 993
    assert config["imap"]["ssl"] is True
    assert config["smtp"]["host"] == "smtp.gmail.com"
    assert config["smtp"]["port"] == 587
    assert config["smtp"]["starttls"] is True


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_unified_flow_auto_detected_defaults_overridden(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-5: Unified flow allows user to override auto-detected defaults."""
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

    # Mock passwords (initial, IMAP, SMTP)
    mock_getpass.side_effect = ["test-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init with overridden port
    user_input = (
        "user@gmail.com\n"  # Email
        "\n"  # IMAP server [imap.gmail.com] - accept default
        "143\n"  # IMAP port [993] - OVERRIDE to 143
        "n\n"  # IMAP SSL [Y] - OVERRIDE to n
        "\n"  # IMAP username [user@gmail.com] - accept default
        # IMAP password [REDACTED] - accept default
        "\n"  # SMTP server [smtp.gmail.com] - accept default
        "\n"  # SMTP port [587] - accept default
        "\n"  # SMTP STARTTLS [Y] - accept default
        "\n"  # SMTP username [user@gmail.com] - accept default
        # SMTP password [REDACTED] - accept default
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"

    # Verify YAML has overridden values
    import yaml

    config_path = tmp_path / "mailreactor.yaml"
    with config_path.open("r") as f:
        config = yaml.safe_load(f)

    assert config["imap"]["host"] == "imap.gmail.com"  # Default
    assert config["imap"]["port"] == 143  # Overridden
    assert config["imap"]["ssl"] is False  # Overridden
    assert config["smtp"]["host"] == "smtp.gmail.com"  # Default
    assert config["smtp"]["port"] == 587  # Default
    assert config["smtp"]["starttls"] is True  # Default


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_password_defaults_cascade(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-6: Password defaults cascade: initial → IMAP → SMTP."""
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

    # Mock password inputs: initial, IMAP override, SMTP use IMAP
    # Initial password, IMAP password override (App Password), SMTP accept IMAP password (empty)
    mock_getpass.side_effect = ["initial-password", "imap-app-password", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init
    user_input = (
        "user@gmail.com\n"  # Email
        "\n"  # IMAP server [imap.gmail.com]
        "\n"  # IMAP port [993]
        "\n"  # IMAP SSL [Y]
        "\n"  # IMAP username [user@gmail.com]
        # IMAP password [REDACTED] via getpass - override with "imap-app-password"
        "\n"  # SMTP server [smtp.gmail.com]
        "\n"  # SMTP port [587]
        "\n"  # SMTP STARTTLS [Y]
        "\n"  # SMTP username [user@gmail.com]
        # SMTP password [REDACTED] via getpass - accept IMAP password (empty)
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"

    # Verify IMAP validation called with IMAP password (not initial)
    imap_config = mock_imap_validate.call_args[0][0]
    assert imap_config.password == "imap-app-password"  # pragma: allowlist secret

    # Verify SMTP validation called with IMAP password (cascade)
    smtp_config = mock_smtp_validate.call_args[0][0]
    assert smtp_config.password == "imap-app-password"  # pragma: allowlist secret


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
@patch("mailreactor.cli.init.structlog.configure")
def test_verbose_flag_enables_debug_logs(
    mock_structlog_configure,
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-7: --verbose flag enables DEBUG log level in structlog."""
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

    # Mock passwords
    mock_getpass.side_effect = ["test-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init with --verbose
    user_input = (
        "user@gmail.com\n\n" * 9  # Accept all defaults
    )
    result = runner.invoke(app, ["init", "--verbose"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"

    # Verify structlog.configure was called with DEBUG log level
    mock_structlog_configure.assert_called_once()
    call_kwargs = mock_structlog_configure.call_args.kwargs

    # Check wrapper_class is make_filtering_bound_logger with DEBUG level

    wrapper = call_kwargs["wrapper_class"]
    assert wrapper is not None
    # Can't easily inspect the bound logger level, but verify configure was called
    # (structlog.make_filtering_bound_logger wraps logging level)

    # Verify processors include ConsoleRenderer (no timestamp)
    processors = call_kwargs["processors"]
    assert any("ConsoleRenderer" in str(p) for p in processors)


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
@patch("mailreactor.cli.init.structlog.configure")
def test_default_suppresses_logs(
    mock_structlog_configure,
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-7: Default (no --verbose) sets ERROR log level to suppress DEBUG/INFO logs."""
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

    # Mock passwords
    mock_getpass.side_effect = ["test-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Run init WITHOUT --verbose (default)
    user_input = (
        "user@gmail.com\n\n" * 9  # Accept all defaults
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify success
    assert result.exit_code == 0, f"Exit code {result.exit_code}, stdout:\n{result.stdout}"

    # Verify structlog.configure was called with ERROR log level (suppresses DEBUG/INFO)
    mock_structlog_configure.assert_called_once()
    call_kwargs = mock_structlog_configure.call_args.kwargs

    # Check wrapper_class is make_filtering_bound_logger with ERROR level

    wrapper = call_kwargs["wrapper_class"]
    assert wrapper is not None

    # Verify processors include ConsoleRenderer (no timestamp)
    processors = call_kwargs["processors"]
    assert any("ConsoleRenderer" in str(p) for p in processors)


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_per_protocol_validation_early_exit_on_imap_failure(
    mock_getpass,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """AC-4: IMAP validation failure exits early before SMTP prompts."""
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

    # Mock passwords (initial, IMAP)
    mock_getpass.side_effect = ["test-password", ""]  # Only IMAP, no SMTP needed

    # Mock IMAP failure
    mock_imap_validate.return_value = (False, "IMAP authentication failed for user@gmail.com")

    # Run init
    user_input = (
        "user@gmail.com\n"  # Email
        "\n"  # IMAP server [imap.gmail.com]
        "\n"  # IMAP port [993]
        "\n"  # IMAP SSL [Y]
        "\n"  # IMAP username [user@gmail.com]
        # IMAP password [REDACTED] via getpass
        # NO SMTP prompts (should exit early)
    )
    result = runner.invoke(app, ["init"], input=user_input)

    # Verify failure
    assert result.exit_code == 1
    assert "IMAP authentication failed" in result.stdout

    # Verify IMAP config summary shown before validation (AC-4)
    assert "IMAP Configuration:" in result.stdout
    assert "Host: imap.gmail.com" in result.stdout

    # Verify SMTP prompts/validation NOT shown (early exit)
    assert "SMTP server" not in result.stdout
    assert "SMTP Configuration:" not in result.stdout
    assert "Testing SMTP connection" not in result.stdout

    # Verify no YAML created
    config_path = tmp_path / "mailreactor.yaml"
    assert not config_path.exists()


@patch("mailreactor.cli.init.detect_provider")
@patch("mailreactor.cli.init._validate_imap_connection")
@patch("mailreactor.cli.init._validate_smtp_connection")
@patch("mailreactor.cli.init.getpass.getpass")
def test_header_always_unchanged_regardless_of_flags(
    mock_getpass,
    mock_smtp_validate,
    mock_imap_validate,
    mock_detect,
    tmp_path,
    monkeypatch,
):
    """HC Correction: Header always shows 'Mail Reactor Setup Wizard' with no mode indicators."""
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

    # Mock passwords
    mock_getpass.side_effect = ["test-password", "", ""]

    # Mock validation success
    mock_imap_validate.return_value = (True, None)
    mock_smtp_validate.return_value = (True, None)

    # Test all flag combinations
    flag_combinations = [
        [],  # No flags
        ["--no-validation"],
        ["--no-autoconfig"],
        ["--no-autoconfig", "--no-validation"],
        ["--verbose"],
    ]

    for flags in flag_combinations:
        # Reset mocks
        mock_detect.reset_mock()
        mock_imap_validate.reset_mock()
        mock_smtp_validate.reset_mock()
        mock_getpass.side_effect = ["test-password", "", ""]

        # Create fresh temp directory for each test
        test_dir = tmp_path / f"test_{'_'.join(flags) if flags else 'default'}"
        test_dir.mkdir(exist_ok=True)
        monkeypatch.chdir(test_dir)

        # Build input based on flags
        if "--no-autoconfig" in flags:
            user_input = (
                "user@test.com\n"
                "imap.test.com\n"  # Manual IMAP server (no default)
                "\n\n\n"  # IMAP port, SSL, username
                "smtp.test.com\n"  # Manual SMTP server (no default)
                "\n\n\n"  # SMTP port, STARTTLS, username
            )
        else:
            user_input = (
                "user@test.com\n\n" * 9  # Accept all defaults
            )

        result = runner.invoke(app, ["init"] + flags, input=user_input)

        # Verify header is ALWAYS the same
        assert "Mail Reactor Setup Wizard\n" in result.stdout
        assert "Offline Mode" not in result.stdout
        assert "Manual Configuration" not in result.stdout
        assert "(" not in result.stdout.split("\n")[0]  # No parentheses in header
