"""Unit tests for CLI server commands.

Tests CLI argument parsing, configuration override, and logging setup
without actually starting the server (using mocks).
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer
from cryptography.fernet import InvalidToken
from typer.testing import CliRunner

# Import app and ensure cli module is loaded before mocking
from mailreactor.__main__ import app
import mailreactor.cli.server  # noqa: F401 - Ensure module is loaded for mocking


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing Typer CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def ensure_cli_module_loaded():
    """Ensure mailreactor.cli.server is loaded before any test runs.

    This prevents AttributeError when performance tests delete mailreactor
    from sys.modules but @patch decorators need to resolve mailreactor.cli.server.
    """
    import sys

    # Force import of cli module if not present
    if "mailreactor.cli.server" not in sys.modules:
        import mailreactor.cli.server  # noqa: F401
    yield


@pytest.fixture
def mock_account_config_loading(monkeypatch):
    """Mock load_account_config for tests that don't explicitly test config loading (Story 2.6).

    This fixture ensures legacy tests continue to work after Story 2.6 added
    config loading to _run_server().
    """
    from unittest.mock import Mock
    from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig

    mock_account_config = AccountConfig(
        email="test@example.com",
        imap=IMAPConfig(
            host="imap.example.com",
            port=993,
            ssl=True,
            username="test@example.com",
            password="test-password",  # pragma: allowlist secret
        ),
        smtp=SMTPConfig(
            host="smtp.example.com",
            port=587,
            starttls=True,
            username="test@example.com",
            password="test-password",  # pragma: allowlist secret
        ),
    )

    mock_func = Mock(return_value=mock_account_config)
    monkeypatch.setattr("mailreactor.cli.server.load_account_config", mock_func)
    yield mock_func


class TestCLIArgumentParsing:
    """Test CLI argument parsing and validation."""

    @pytest.fixture(autouse=True)
    def _mock_config(self, mock_account_config_loading):
        """Use config loading mock for all tests in this class."""
        pass

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_with_defaults(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test start command with default arguments."""
        result = cli_runner.invoke(app, ["start"])

        assert result.exit_code == 0
        # Verify logging configured with defaults
        mock_configure_logging.assert_called_once_with(json_format=False, log_level="INFO")
        # Verify uvicorn started with defaults (now uses factory pattern)
        mock_uvicorn_run.assert_called_once()
        call_args = mock_uvicorn_run.call_args
        assert call_args[0][0] == "mailreactor.main:create_app"  # Import string
        assert call_args[1]["host"] == "127.0.0.1"
        assert call_args[1]["port"] == 8000
        assert call_args[1]["log_level"] == "info"
        assert call_args[1]["factory"] is True

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_with_custom_host_and_port(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test start command with custom host and port."""
        result = cli_runner.invoke(app, ["start", "--host", "0.0.0.0", "--port", "3000"])

        assert result.exit_code == 0
        call_args = mock_uvicorn_run.call_args
        assert call_args[1]["host"] == "0.0.0.0"
        assert call_args[1]["port"] == 3000

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_with_json_logs(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test start command with JSON logging enabled."""
        result = cli_runner.invoke(app, ["start", "--json-logs"])

        assert result.exit_code == 0
        # Verify JSON logging enabled
        mock_configure_logging.assert_called_once_with(json_format=True, log_level="INFO")

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_with_debug_log_level(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test start command with DEBUG log level."""
        result = cli_runner.invoke(app, ["start", "--log-level", "DEBUG"])

        assert result.exit_code == 0
        # Verify DEBUG log level
        mock_configure_logging.assert_called_once_with(json_format=False, log_level="DEBUG")
        call_args = mock_uvicorn_run.call_args
        assert call_args[1]["log_level"] == "debug"

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_with_case_insensitive_log_level(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test start command accepts case-insensitive log level."""
        result = cli_runner.invoke(app, ["start", "--log-level", "warning"])

        assert result.exit_code == 0
        # Verify case is normalized to uppercase
        mock_configure_logging.assert_called_once_with(json_format=False, log_level="WARNING")

    # Removed: test_start_command_with_account_flag_shows_warning
    # --account flag removed in Story 2.6, replaced with --config flag

    def test_start_command_invalid_port_rejected(self, cli_runner: CliRunner) -> None:
        """Test start command rejects invalid port number."""
        result = cli_runner.invoke(app, ["start", "--port", "99999"])

        # Typer should reject port > 65535
        assert result.exit_code != 0
        assert "99999" in result.output or "Invalid value" in result.output


class TestCLILoggingConfiguration:
    """Test logging configuration from CLI flags."""

    @pytest.fixture(autouse=True)
    def _mock_config(self, mock_account_config_loading):
        """Use config loading mock for all tests in this class."""
        pass

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_configure_logging_called_before_uvicorn(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test configure_logging is called BEFORE uvicorn.run."""
        call_order = []
        mock_configure_logging.side_effect = lambda **kwargs: call_order.append("logging")
        mock_uvicorn_run.side_effect = lambda *args, **kwargs: call_order.append("uvicorn")

        result = cli_runner.invoke(app, ["start"])

        # Verify order: logging first, then uvicorn
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert call_order == ["logging", "uvicorn"]

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_logging_configuration_with_all_options(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test logging configuration with all CLI options."""
        cli_runner.invoke(
            app,
            ["start", "--log-level", "ERROR", "--json-logs"],
        )

        # Verify both flags passed to configure_logging
        mock_configure_logging.assert_called_once_with(json_format=True, log_level="ERROR")


class TestCLISettingsOverride:
    """Test Settings override with CLI flags."""

    @pytest.fixture(autouse=True)
    def _mock_config(self, mock_account_config_loading):
        """Use config loading mock for all tests in this class."""
        pass

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    @patch("mailreactor.cli.server.Settings")
    def test_settings_overridden_by_cli_flags(
        self,
        mock_settings_class: Mock,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test Settings instance created with CLI flag overrides."""
        mock_settings = MagicMock()
        mock_settings.host = "192.168.1.1"
        mock_settings.port = 9000
        mock_settings.log_level = "DEBUG"
        mock_settings_class.return_value = mock_settings

        cli_runner.invoke(
            app,
            ["start", "--host", "192.168.1.1", "--port", "9000", "--log-level", "DEBUG"],
        )

        # Verify Settings instantiated with CLI values
        mock_settings_class.assert_called_once_with(
            host="192.168.1.1",
            port=9000,
            log_level="DEBUG",
            json_logs=False,
        )


class TestCLIHelpText:
    """Test CLI help text and documentation."""

    # No mock needed - help text doesn't execute the command

    def test_start_command_help_displayed(self, cli_runner: CliRunner) -> None:
        """Test start command --help displays usage information."""
        result = cli_runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0
        # Verify help text includes key information
        assert "Start Mail Reactor API server" in result.output
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--log-level" in result.output
        assert "--json-logs" in result.output
        assert "--config" in result.output

    def test_start_command_help_includes_examples(self, cli_runner: CliRunner) -> None:
        """Test start command --help includes usage examples."""
        result = cli_runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0
        # Help text should mention security (localhost default)
        assert "localhost" in result.output.lower() or "127.0.0.1" in result.output

    def test_root_help_includes_start_command(self, cli_runner: CliRunner) -> None:
        """Test root --help lists start command."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "start" in result.output


class TestCLISecurityDefaults:
    """Test security-related defaults (localhost binding)."""

    @pytest.fixture(autouse=True)
    def _mock_config(self, mock_account_config_loading):
        """Use config loading mock for all tests in this class."""
        pass

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_default_host_is_localhost(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test default host is 127.0.0.1 (localhost) for security."""
        result = cli_runner.invoke(app, ["start"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_uvicorn_run.call_args
        assert call_args[1]["host"] == "127.0.0.1"

    @patch("mailreactor.cli.server.logger")
    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_binding_to_all_interfaces_logs_warning(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        mock_logger: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test binding to 0.0.0.0 logs security warning."""
        result = cli_runner.invoke(app, ["start", "--host", "0.0.0.0"])

        assert result.exit_code == 0
        # Verify security warning was logged
        mock_logger.warning.assert_any_call(
            "network_exposure",
            message="Server binding to 0.0.0.0 exposes API to network. "
            "Ensure authentication is configured (Epic 5).",
        )


class TestDevCommand:
    """Test dev command with auto-reload (Story 1.8)."""

    @pytest.fixture(autouse=True)
    def _mock_config(self, mock_account_config_loading):
        """Use config loading mock for all tests in this class."""
        pass

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_with_defaults(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test dev command with default arguments."""
        result = cli_runner.invoke(app, ["dev"])

        assert result.exit_code == 0
        # Verify logging configured with DEBUG default
        mock_configure_logging.assert_called_once_with(json_format=False, log_level="DEBUG")
        # Verify uvicorn started with reload enabled
        # Note: dev command passes import string to uvicorn (auto-detects factory)
        mock_uvicorn_run.assert_called_once()
        call_args = mock_uvicorn_run.call_args
        assert call_args[0][0] == "mailreactor.main:create_app"  # Import string, not instance
        assert call_args[1]["host"] == "127.0.0.1"
        assert call_args[1]["port"] == 8000
        assert call_args[1]["reload"] is True
        assert call_args[1]["reload_dirs"] == ["src/mailreactor"]
        assert call_args[1]["reload_delay"] == 0.5
        assert call_args[1]["log_level"] == "debug"

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_default_log_level_is_debug(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test dev command defaults to DEBUG log level (not INFO)."""
        result = cli_runner.invoke(app, ["dev"])

        assert result.exit_code == 0
        mock_configure_logging.assert_called_once_with(json_format=False, log_level="DEBUG")

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_with_custom_host_and_port(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test dev command with custom host and port."""
        result = cli_runner.invoke(app, ["dev", "--host", "0.0.0.0", "--port", "3000"])

        assert result.exit_code == 0
        call_args = mock_uvicorn_run.call_args
        assert call_args[1]["host"] == "0.0.0.0"
        assert call_args[1]["port"] == 3000
        assert call_args[1]["reload"] is True  # Still enabled in dev mode

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_with_info_log_level_override(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test dev command log level can be overridden to INFO."""
        result = cli_runner.invoke(app, ["dev", "--log-level", "INFO"])

        assert result.exit_code == 0
        mock_configure_logging.assert_called_once_with(json_format=False, log_level="INFO")

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_with_json_logs(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test dev command with JSON logging enabled."""
        result = cli_runner.invoke(app, ["dev", "--json-logs"])

        assert result.exit_code == 0
        mock_configure_logging.assert_called_once_with(json_format=True, log_level="DEBUG")

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_reload_configuration(
        self,
        mock_configure_logging: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test dev command configures uvicorn reload correctly."""
        result = cli_runner.invoke(app, ["dev"])

        assert result.exit_code == 0
        call_args = mock_uvicorn_run.call_args
        # Verify reload configuration
        assert call_args[1]["reload"] is True
        assert call_args[1]["reload_dirs"] == ["src/mailreactor"]
        assert call_args[1]["reload_delay"] == 0.5

    def test_dev_command_help_displayed(self, cli_runner: CliRunner) -> None:
        """Test dev command --help displays usage information."""
        result = cli_runner.invoke(app, ["dev", "--help"])

        assert result.exit_code == 0
        assert "development" in result.output.lower()
        assert "auto-reload" in result.output.lower()
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--log-level" in result.output
        assert "--json-logs" in result.output

    def test_root_help_includes_dev_command(self, cli_runner: CliRunner) -> None:
        """Test root --help lists dev command."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "dev" in result.output


class TestLoadAccountConfig:
    """Test load_account_config function (Story 2.6)."""

    @patch("mailreactor.cli.server.AccountConfig.from_yaml")
    @patch("mailreactor.cli.server.load_config")
    @patch("mailreactor.cli.server.getpass.getpass")
    @patch("mailreactor.cli.server.logger")
    def test_load_account_config_success_with_prompt(
        self,
        mock_logger: Mock,
        mock_getpass: Mock,
        mock_load_config: Mock,
        mock_from_yaml: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test load_account_config with correct password from prompt."""
        from mailreactor.cli.server import load_account_config
        from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig

        # Clear env var so getpass is used instead
        monkeypatch.delenv("MAILREACTOR_PASSWORD", raising=False)

        # Setup mocks
        config_file = tmp_path / "mailreactor.yaml"
        config_file.touch()
        mock_load_config.return_value = {"email": "test@example.com"}
        mock_getpass.return_value = "correct-password"  # pragma: allowlist secret
        mock_account_config = AccountConfig(
            email="test@example.com",
            imap=IMAPConfig(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.example.com",
                port=587,
                starttls=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
        )
        mock_from_yaml.return_value = mock_account_config

        # Execute
        result = load_account_config(config_file)

        # Verify
        assert result == mock_account_config
        mock_load_config.assert_called_once_with(config_file)
        mock_from_yaml.assert_called_once_with({"email": "test@example.com"}, "correct-password")
        mock_logger.info.assert_any_call("config_loaded", path=str(config_file))
        mock_logger.info.assert_any_call(
            "account_configured",
            email="test@example.com",
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
        )

    @patch("mailreactor.cli.server.AccountConfig.from_yaml")
    @patch("mailreactor.cli.server.load_config")
    @patch("mailreactor.cli.server.logger")
    def test_load_account_config_success_with_env_var(
        self,
        mock_logger: Mock,
        mock_load_config: Mock,
        mock_from_yaml: Mock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test load_account_config with master password from environment variable."""
        from mailreactor.cli.server import load_account_config
        from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig

        # Setup mocks and environment
        config_file = tmp_path / "mailreactor.yaml"
        config_file.touch()
        monkeypatch.setenv("MAILREACTOR_PASSWORD", "env-password")  # pragma: allowlist secret
        mock_load_config.return_value = {"email": "test@example.com"}
        mock_account_config = AccountConfig(
            email="test@example.com",
            imap=IMAPConfig(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.example.com",
                port=587,
                starttls=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
        )
        mock_from_yaml.return_value = mock_account_config

        # Execute
        result = load_account_config(config_file)

        # Verify
        assert result == mock_account_config
        mock_from_yaml.assert_called_once_with({"email": "test@example.com"}, "env-password")
        # Verify new log event (INFO level, not DEBUG)
        mock_logger.info.assert_any_call("master_password", from_env="MAILREACTOR_PASSWORD")

    @patch("mailreactor.cli.server.logger")
    def test_load_account_config_missing_file(
        self,
        mock_logger: Mock,
        tmp_path: Path,
    ) -> None:
        """Test load_account_config with missing config file."""
        from mailreactor.cli.server import load_account_config

        # Setup - no file exists
        config_file = tmp_path / "nonexistent.yaml"

        # Execute and verify
        with pytest.raises(typer.Exit) as exc_info:
            load_account_config(config_file)

        assert exc_info.value.exit_code == 1
        mock_logger.error.assert_called_once_with(
            "config_not_found",
            path=str(config_file),
            help="run 'mailreactor init' or 'mailreactor start --config path/to/yaml'",
        )

    @patch("mailreactor.cli.server.AccountConfig.from_yaml")
    @patch("mailreactor.cli.server.load_config")
    @patch("mailreactor.cli.server.getpass.getpass")
    @patch("mailreactor.cli.server.logger")
    def test_load_account_config_wrong_password(
        self,
        mock_logger: Mock,
        mock_getpass: Mock,
        mock_load_config: Mock,
        mock_from_yaml: Mock,
        tmp_path: Path,
    ) -> None:
        """Test load_account_config with wrong master password."""
        from mailreactor.cli.server import load_account_config

        # Setup mocks
        config_file = tmp_path / "mailreactor.yaml"
        config_file.touch()
        mock_load_config.return_value = {"email": "test@example.com"}
        mock_getpass.return_value = "wrong-password"
        mock_from_yaml.side_effect = InvalidToken()

        # Execute and verify
        with pytest.raises(typer.Exit) as exc_info:
            load_account_config(config_file)

        assert exc_info.value.exit_code == 1
        mock_logger.error.assert_called_with("decryption_failed", reason="invalid_master_password")

    @patch("mailreactor.cli.server.load_config")
    @patch("mailreactor.cli.server.getpass.getpass")
    @patch("mailreactor.cli.server.logger")
    def test_load_account_config_corrupted_yaml(
        self,
        mock_logger: Mock,
        mock_getpass: Mock,
        mock_load_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test load_account_config with corrupted YAML file."""
        from mailreactor.cli.server import load_account_config

        # Setup mocks
        config_file = tmp_path / "mailreactor.yaml"
        config_file.touch()
        mock_getpass.return_value = "test-password"
        mock_load_config.side_effect = Exception("YAML parse error")

        # Execute and verify
        with pytest.raises(typer.Exit) as exc_info:
            load_account_config(config_file)

        assert exc_info.value.exit_code == 1
        mock_logger.error.assert_called_with(
            "config_parse_error", error="YAML parse error", error_type="Exception"
        )


class TestStartCommandWithConfig:
    """Test start command with --config flag (Story 2.6)."""

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.load_account_config")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_with_config_flag(
        self,
        mock_configure_logging: Mock,
        mock_load_account_config: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test start command with --config flag."""
        from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig

        # Setup mocks
        config_file = tmp_path / "custom.yaml"
        mock_account_config = AccountConfig(
            email="test@example.com",
            imap=IMAPConfig(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.example.com",
                port=587,
                starttls=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
        )
        mock_load_account_config.return_value = mock_account_config

        # Execute
        result = cli_runner.invoke(app, ["start", "--config", str(config_file)])

        # Verify
        assert result.exit_code == 0
        mock_load_account_config.assert_called_once()
        call_args = mock_load_account_config.call_args[0][0]
        assert str(call_args) == str(config_file)

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.load_account_config")
    @patch("mailreactor.cli.server.configure_logging")
    def test_start_command_without_config_flag_uses_default(
        self,
        mock_configure_logging: Mock,
        mock_load_account_config: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
    ) -> None:
        """Test start command without --config flag uses mailreactor.yaml."""
        from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig

        # Setup mocks
        mock_account_config = AccountConfig(
            email="test@example.com",
            imap=IMAPConfig(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.example.com",
                port=587,
                starttls=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
        )
        mock_load_account_config.return_value = mock_account_config

        # Execute
        result = cli_runner.invoke(app, ["start"])

        # Verify
        assert result.exit_code == 0
        mock_load_account_config.assert_called_once()
        call_args = mock_load_account_config.call_args[0][0]
        assert call_args == Path("mailreactor.yaml")

    def test_start_command_help_shows_config_flag(self, cli_runner: CliRunner) -> None:
        """Test start command --help shows --config flag."""
        result = cli_runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0
        assert "--config" in result.output
        assert "mailreactor.yaml" in result.output.lower()

    def test_start_command_help_no_account_flag(self, cli_runner: CliRunner) -> None:
        """Test start command --help does NOT show --account flag."""
        result = cli_runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0
        # --account flag should be removed
        assert "--account" not in result.output


class TestDevCommandWithConfig:
    """Test dev command with --config flag (Story 2.6)."""

    @patch("mailreactor.cli.server.uvicorn.run")
    @patch("mailreactor.cli.server.load_account_config")
    @patch("mailreactor.cli.server.configure_logging")
    def test_dev_command_with_config_flag(
        self,
        mock_configure_logging: Mock,
        mock_load_account_config: Mock,
        mock_uvicorn_run: Mock,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test dev command with --config flag."""
        from mailreactor.models.account import AccountConfig, IMAPConfig, SMTPConfig

        # Setup mocks
        config_file = tmp_path / "custom.yaml"
        mock_account_config = AccountConfig(
            email="test@example.com",
            imap=IMAPConfig(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
            smtp=SMTPConfig(
                host="smtp.example.com",
                port=587,
                starttls=True,
                username="test@example.com",
                password="decrypted-password",  # pragma: allowlist secret
            ),
        )
        mock_load_account_config.return_value = mock_account_config

        # Execute
        result = cli_runner.invoke(app, ["dev", "--config", str(config_file)])

        # Verify
        assert result.exit_code == 0
        mock_load_account_config.assert_called_once()
        call_args = mock_load_account_config.call_args[0][0]
        assert str(call_args) == str(config_file)

    def test_dev_command_help_shows_config_flag(self, cli_runner: CliRunner) -> None:
        """Test dev command --help shows --config flag."""
        result = cli_runner.invoke(app, ["dev", "--help"])

        assert result.exit_code == 0
        assert "--config" in result.output

    def test_dev_command_help_no_account_flag(self, cli_runner: CliRunner) -> None:
        """Test dev command --help does NOT show --account flag."""
        result = cli_runner.invoke(app, ["dev", "--help"])

        assert result.exit_code == 0
        # --account flag should be removed
        assert "--account" not in result.output
