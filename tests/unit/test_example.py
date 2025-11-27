"""
Example unit test for Mail Reactor.

Unit tests focus on pure Python logic with no external dependencies.
Use Python mocks for any external services (IMAP, SMTP, etc).
"""

import pytest


@pytest.mark.unit
def test_example_unit():
    """Example unit test that always passes."""
    assert 1 + 1 == 2


@pytest.mark.unit
def test_example_with_mock(mock_account_credentials):
    """Example unit test using a fixture from conftest.py"""
    creds = mock_account_credentials
    assert creds["email"] == "test@example.com"
    assert "password" in creds
    assert creds["imap_host"] == "imap.example.com"


@pytest.mark.unit
@pytest.mark.parametrize(
    "email,expected_domain",
    [
        ("user@gmail.com", "gmail.com"),
        ("test@outlook.com", "outlook.com"),
        ("admin@example.com", "example.com"),
    ],
)
def test_example_parametrized(email, expected_domain):
    """Example parametrized test for testing multiple inputs."""
    # Extract domain from email
    domain = email.split("@")[1]
    assert domain == expected_domain


@pytest.mark.unit
def test_example_mock_imap(mock_imap_client):
    """Example test using mock IMAP client."""
    # Mock IMAP client is already configured in conftest.py
    mock_imap_client.search.return_value = [1, 2, 3]

    # Test code would call the mock
    result = mock_imap_client.search(["UNSEEN"])

    # Verify mock was called correctly
    assert result == [1, 2, 3]
    mock_imap_client.search.assert_called_once_with(["UNSEEN"])


@pytest.mark.unit
def test_example_email_parsing(mock_email_message):
    """Example test using mock email message fixture."""
    msg = mock_email_message

    # Verify message structure
    assert msg["subject"] == "Test Email"
    assert msg["from"] == "sender@example.com"
    assert "recipient@example.com" in msg["to"]
    assert msg["body_plain"] == "This is a test email body."
