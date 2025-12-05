"""
Security tests for credential leak detection.

Validates NFR-S1: Credentials never logged or exposed in responses.

These tests scan logs and responses for credential patterns to ensure
passwords, API keys, and secrets never leak to users or log files.
"""

import pytest
import re
from typing import List, Pattern


# Credential patterns to detect in logs/responses
CREDENTIAL_PATTERNS: List[Pattern] = [
    re.compile(r'password\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'api[_-]?key\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'secret\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'token\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r"bearer\s+([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
]


@pytest.mark.security
@pytest.mark.unit
def test_credential_patterns_detection():
    """Verify credential detection patterns work correctly."""
    # Test cases with known credentials
    test_cases = [
        ('password="secret123"', True),  # pragma: allowlist secret
        ('api_key="abc-def-123"', True),  # pragma: allowlist secret
        ('secret: "my-secret-value"', True),  # pragma: allowlist secret
        ('token="bearer-token-here"', True),
        ("bearer abc123xyz", True),
        ('email="test@example.com"', False),
        ("username: admin", False),
    ]

    for text, should_match in test_cases:
        found_credential = any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS)
        assert found_credential == should_match, f"Pattern detection failed for: {text}"


@pytest.mark.security
@pytest.mark.unit
def test_credentials_not_in_log_example(caplog):
    """
    Example test: Verify credentials never appear in logs.

    This test will be expanded when logging is implemented (Story 1.3).
    For now, it tests the pattern matching logic.
    """
    # Simulate a log entry WITHOUT credentials (good)
    safe_log = "INFO: Account connected email=test@example.com host=imap.example.com"

    # Check that no credential patterns match
    for pattern in CREDENTIAL_PATTERNS:
        matches = pattern.findall(safe_log)
        assert len(matches) == 0, f"Found potential credential in log: {matches}"


@pytest.mark.security
@pytest.mark.unit
def test_credentials_in_log_would_fail():
    """
    Example test: Show what happens if credentials ARE logged (bad).

    This test demonstrates that our detection would catch leaked credentials.
    """
    # Simulate a log entry WITH credentials (bad - should never happen)
    unsafe_log = 'ERROR: Login failed with password="supersecret123" for user test@example.com'  # pragma: allowlist secret

    # Verify our patterns WOULD detect this
    found_credentials = []
    for pattern in CREDENTIAL_PATTERNS:
        matches = pattern.findall(unsafe_log)
        found_credentials.extend(matches)

    # We EXPECT to find credentials here (this is the unsafe case)
    assert len(found_credentials) > 0, "Credential detection failed - should have found password"
    assert "supersecret123" in found_credentials[0]


@pytest.mark.security
@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_error_no_password_leak_placeholder(api_client):
    """
    Test that API errors don't leak passwords in responses.

    This will be implemented after Story 2.4 (Account Connection Validation).
    """
    pytest.skip("API error handling not yet implemented (Story 1.7, Story 2.4)")

    # Future implementation:
    # response = await api_client.post("/accounts", json={
    #     "email": "test@example.com",
    #     "password": "WrongPassword123!",  # pragma: allowlist secret
    #     "imap_host": "imap.example.com"
    # })
    #
    # assert response.status_code in [401, 400]
    #
    # # Verify password does NOT appear in error response
    # response_text = response.text.lower()
    # assert "wrongpassword123!" not in response_text
    # assert "password" not in response.json().get("detail", "").lower()


@pytest.mark.security
@pytest.mark.unit
def test_pydantic_model_excludes_credentials():
    """
    Security test: Verify Pydantic models exclude credentials from serialization.

    Validates NFR-S1: Passwords never exposed in API responses or logs.
    Tests that IMAPConfig, SMTPConfig, and MailAccount properly exclude passwords.
    """
    from mailreactor.models.account import MailAccount, IMAPConfig, SMTPConfig

    # Create account with sensitive credentials
    account = MailAccount(
        account_id="acc_test123",
        email="security-test@example.com",
        imap=IMAPConfig(
            host="imap.example.com",
            username="imap-user",
            password="SuperSecret-IMAP-Password123!",  # pragma: allowlist secret
        ),
        smtp=SMTPConfig(
            host="smtp.example.com",
            username="smtp-user",
            password="SuperSecret-SMTP-Password456!",  # pragma: allowlist secret
        ),
    )

    # Test 1: Verify passwords excluded from dict serialization
    account_dict = account.model_dump()
    assert "password" not in account_dict.get("imap", {}), "IMAP password leaked in model_dump()"
    assert "password" not in account_dict.get("smtp", {}), "SMTP password leaked in model_dump()"

    # Test 2: Verify passwords excluded from JSON serialization
    account_json = account.model_dump_json()
    assert "SuperSecret-IMAP-Password123!" not in account_json, "IMAP password leaked in JSON"
    assert "SuperSecret-SMTP-Password456!" not in account_json, "SMTP password leaked in JSON"

    # Test 3: Scan JSON for credential patterns (security scanner check)
    found_credentials = []
    for pattern in CREDENTIAL_PATTERNS:
        matches = pattern.findall(account_json)
        found_credentials.extend(matches)

    assert len(found_credentials) == 0, (
        f"SECURITY VIOLATION: Credential patterns detected in serialized MailAccount: {found_credentials}"
    )

    # Test 4: Verify IMAP/SMTP configs individually also exclude passwords
    imap_json = account.imap.model_dump_json()
    smtp_json = account.smtp.model_dump_json()

    assert "SuperSecret-IMAP-Password123!" not in imap_json, (
        "IMAP password leaked in IMAPConfig JSON"
    )
    assert "SuperSecret-SMTP-Password456!" not in smtp_json, (
        "SMTP password leaked in SMTPConfig JSON"
    )


@pytest.mark.security
@pytest.mark.integration
def test_log_scanner_integration_placeholder(caplog):
    """
    Integration test: Scan all captured logs for credential leaks.

    This will be run as part of integration test suite to catch any
    accidental credential logging across the entire application.
    """
    pytest.skip("Application logging not yet implemented (Story 1.3)")

    # Future implementation:
    # # Run some application code that generates logs
    # # ... application code here ...
    #
    # # Scan all captured logs
    # all_logs = caplog.text
    #
    # found_credentials = []
    # for pattern in CREDENTIAL_PATTERNS:
    #     matches = pattern.findall(all_logs)
    #     found_credentials.extend(matches)
    #
    # # Fail if ANY credentials found in logs
    # assert len(found_credentials) == 0, (
    #     f"SECURITY VIOLATION: Found {len(found_credentials)} potential "
    #     f"credentials in logs: {found_credentials[:5]}"
    # )


@pytest.mark.security
@pytest.mark.unit
def test_mock_credentials_are_safe(mock_account_credentials):
    """Verify test fixtures don't use real credentials."""
    # Use the fixture injected by pytest
    creds = mock_account_credentials

    # Verify mock passwords contain "fake" or "test" or "do-not-use"
    fake_indicators = ["fake", "test", "do-not-use", "mock", "example"]

    # Check that fixture password is clearly fake
    mock_password = creds["password"]

    is_obviously_fake = any(indicator in mock_password.lower() for indicator in fake_indicators)
    assert is_obviously_fake, f"Mock password '{mock_password}' should be obviously fake"
