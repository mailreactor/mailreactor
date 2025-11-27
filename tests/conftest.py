"""
Shared pytest fixtures for Mail Reactor tests.

This file provides reusable fixtures for unit, integration, and E2E tests.
Uses Python mocks (unittest.mock) for fast, isolated testing.
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from httpx import AsyncClient
from typing import AsyncGenerator, Dict, Any


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================


@pytest.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """
    FastAPI test client for integration tests.

    Uses httpx.AsyncClient with in-memory HTTP (no network calls).
    Import app only when fixture is used to avoid circular dependencies.

    Usage:
        async def test_health(api_client):
            response = await api_client.get("/health")
            assert response.status_code == 200
    """
    # Lazy import to avoid issues if app not yet created
    try:
        from mailreactor.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    except ImportError:
        # If app doesn't exist yet, provide a mock client
        pytest.skip("FastAPI app not yet implemented")


# ============================================================================
# Mock IMAP Client Fixtures (Python mocks - NO Greenmail)
# ============================================================================


@pytest.fixture
def mock_imap_client() -> Mock:
    """
    Mock IMAPClient for unit and integration tests.

    Returns a Mock object that simulates imapclient.IMAPClient behavior.
    NO network calls - pure Python mock.

    Usage:
        def test_imap_search(mock_imap_client):
            mock_imap_client.search.return_value = [1, 2, 3]
            result = mock_imap_client.search(['UNSEEN'])
            assert result == [1, 2, 3]
    """
    mock = MagicMock()

    # Configure common IMAP methods
    mock.login = Mock(return_value=True)
    mock.logout = Mock(return_value=None)
    mock.select_folder = Mock(return_value={"EXISTS": 10})
    mock.search = Mock(return_value=[1, 2, 3])
    mock.fetch = Mock(
        return_value={
            1: {
                b"RFC822": b"From: test@example.com\r\nTo: recipient@example.com\r\nSubject: Test\r\n\r\nTest body",
                b"FLAGS": (b"\\Seen",),
            }
        }
    )
    mock.list_folders = Mock(
        return_value=[
            (("\\HasNoChildren",), "/", "INBOX"),
            (("\\HasNoChildren",), "/", "Sent"),
        ]
    )

    return mock


@pytest.fixture
def mock_async_imap_client() -> AsyncMock:
    """
    Mock async IMAP client for integration tests.

    Returns an AsyncMock that simulates AsyncIMAPClient behavior.
    Use this for testing async IMAP operations.

    Usage:
        async def test_async_imap(mock_async_imap_client):
            mock_async_imap_client.search.return_value = [1, 2, 3]
            result = await mock_async_imap_client.search(['UNSEEN'])
            assert result == [1, 2, 3]
    """
    mock = AsyncMock()

    # Configure common async IMAP methods
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock(return_value=None)
    mock.login = AsyncMock(return_value=True)
    mock.search = AsyncMock(return_value=[1, 2, 3])
    mock.fetch = AsyncMock(
        return_value={
            1: {
                "envelope": {
                    "from": "test@example.com",
                    "to": "recipient@example.com",
                    "subject": "Test Subject",
                },
                "body": "Test email body",
                "flags": ["\\Seen"],
            }
        }
    )

    return mock


# ============================================================================
# Mock SMTP Client Fixtures (Python mocks - NO Greenmail)
# ============================================================================


@pytest.fixture
def mock_smtp_client() -> Mock:
    """
    Mock SMTP client for unit tests.

    Returns a Mock that simulates smtplib.SMTP behavior.
    NO network calls - pure Python mock.

    Usage:
        def test_smtp_send(mock_smtp_client):
            mock_smtp_client.send_message.return_value = {}
            result = mock_smtp_client.send_message(msg)
            assert result == {}
    """
    mock = MagicMock()

    # Configure common SMTP methods
    mock.connect = Mock(return_value=(220, b"smtp.example.com"))
    mock.login = Mock(return_value=(235, b"Authentication successful"))
    mock.send_message = Mock(return_value={})
    mock.quit = Mock(return_value=(221, b"Bye"))

    return mock


@pytest.fixture
def mock_async_smtp_client() -> AsyncMock:
    """
    Mock async SMTP client for integration tests.

    Returns an AsyncMock that simulates aiosmtplib.SMTP behavior.
    Use this for testing async SMTP operations.

    Usage:
        async def test_async_smtp(mock_async_smtp_client):
            mock_async_smtp_client.send_message.return_value = {}
            result = await mock_async_smtp_client.send_message(msg)
            assert result == {}
    """
    mock = AsyncMock()

    # Configure common async SMTP methods
    mock.connect = AsyncMock(return_value=(220, "smtp.example.com"))
    mock.login = AsyncMock(return_value=(235, "Authentication successful"))
    mock.send_message = AsyncMock(return_value={})
    mock.quit = AsyncMock(return_value=(221, "Bye"))

    return mock


# ============================================================================
# Mock Account Credentials Fixtures
# ============================================================================


@pytest.fixture
def mock_account_credentials() -> Dict[str, Any]:
    """
    Mock account credentials for testing.

    Returns a dictionary with fake credentials.
    DO NOT use real credentials in tests.

    Usage:
        def test_account(mock_account_credentials):
            creds = mock_account_credentials
            assert creds['email'] == 'test@example.com'
    """
    return {
        "email": "test@example.com",
        "password": "fake-password-do-not-use-in-prod",
        "imap_host": "imap.example.com",
        "imap_port": 993,
        "imap_ssl": True,
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "smtp_starttls": True,
    }


@pytest.fixture
def mock_gmail_credentials() -> Dict[str, Any]:
    """Mock Gmail account credentials for testing."""
    return {
        "email": "test@gmail.com",
        "password": "fake-gmail-password",
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "imap_ssl": True,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_ssl": False,
        "smtp_starttls": True,
    }


# ============================================================================
# Mock Email Message Fixtures
# ============================================================================


@pytest.fixture
def mock_email_message() -> Dict[str, Any]:
    """
    Mock email message for testing.

    Returns a dictionary representing a parsed email message.

    Usage:
        def test_email_parser(mock_email_message):
            msg = mock_email_message
            assert msg['subject'] == 'Test Email'
    """
    return {
        "id": "12345",
        "message_id": "<12345@example.com>",
        "from": "sender@example.com",
        "to": ["recipient@example.com"],
        "cc": [],
        "bcc": [],
        "subject": "Test Email",
        "body_plain": "This is a test email body.",
        "body_html": "<p>This is a test email body.</p>",
        "date": "2025-11-27T12:00:00Z",
        "flags": ["\\Seen"],
        "attachments": [],
    }


@pytest.fixture
def mock_email_with_attachment() -> Dict[str, Any]:
    """Mock email message with attachment for testing."""
    return {
        "id": "67890",
        "message_id": "<67890@example.com>",
        "from": "sender@example.com",
        "to": ["recipient@example.com"],
        "cc": [],
        "bcc": [],
        "subject": "Email with Attachment",
        "body_plain": "See attached file.",
        "body_html": "<p>See attached file.</p>",
        "date": "2025-11-27T12:00:00Z",
        "flags": [],
        "attachments": [
            {
                "filename": "test.pdf",
                "content_type": "application/pdf",
                "size": 1024,
                "content": "base64-encoded-content-here",
            }
        ],
    }


# ============================================================================
# Real IMAP/SMTP Server Fixtures (Greenmail - for E2E tests)
# ============================================================================


@pytest.fixture(scope="session")
def greenmail_host():
    """Greenmail server connection details."""
    return {
        "imap_host": "localhost",
        "imap_port": 3143,
        "imap_ssl": False,
        "smtp_host": "localhost",
        "smtp_port": 3025,
        "smtp_ssl": False,
    }


@pytest.fixture(scope="session")
def greenmail_test_account():
    """
    Test account credentials for Greenmail.

    Greenmail auto-creates accounts on first login.
    Default test account: test@localhost / test
    """
    return {
        "email": "test@localhost",
        "password": "test",
        "imap_host": "localhost",
        "imap_port": 3143,
        "imap_ssl": False,
        "smtp_host": "localhost",
        "smtp_port": 3025,
        "smtp_ssl": False,
    }


@pytest.fixture
def greenmail_imap_client(greenmail_test_account):
    """
    Real IMAP client connected to Greenmail (for E2E tests).

    Requires Greenmail running:
        cd tests && docker compose -f docker-compose.test.yml up -d

    Usage:
        @pytest.mark.e2e
        def test_real_imap(greenmail_imap_client):
            messages = greenmail_imap_client.search(['ALL'])
            assert isinstance(messages, list)
    """
    try:
        from imapclient import IMAPClient
    except ImportError:
        pytest.skip("IMAPClient not installed (will be added in Epic 2)")

    creds = greenmail_test_account
    client = IMAPClient(creds["imap_host"], port=creds["imap_port"], ssl=creds["imap_ssl"])

    try:
        client.login(creds["email"], creds["password"])
        client.select_folder("INBOX")
        yield client
    finally:
        try:
            client.logout()
        except Exception:
            pass  # Ignore logout errors


@pytest.fixture
def greenmail_smtp_client(greenmail_test_account):
    """
    Real SMTP client connected to Greenmail (for E2E tests).

    Requires Greenmail running:
        cd tests && docker compose -f docker-compose.test.yml up -d

    Usage:
        @pytest.mark.e2e
        def test_real_smtp(greenmail_smtp_client):
            greenmail_smtp_client.send_message(msg)
    """
    try:
        import smtplib
    except ImportError:
        pytest.skip("smtplib required for SMTP tests")

    creds = greenmail_test_account
    smtp = smtplib.SMTP(creds["smtp_host"], creds["smtp_port"])

    try:
        # Note: Greenmail doesn't require STARTTLS or LOGIN for basic sending
        yield smtp
    finally:
        try:
            smtp.quit()
        except Exception:
            pass  # Ignore quit errors


# ============================================================================
# Test Markers Configuration
# ============================================================================


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no network, no external dependencies)"
    )
    config.addinivalue_line("markers", "integration: Integration tests (API endpoints with mocks)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (real servers, slow)")
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
    config.addinivalue_line("markers", "security: Security-focused tests")
    config.addinivalue_line("markers", "soak: Long-running stability tests (4+ hours)")
    config.addinivalue_line("markers", "performance: Performance tests")
