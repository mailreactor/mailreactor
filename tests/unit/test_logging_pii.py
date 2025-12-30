"""Unit tests for PII masking in logging.

Tests verify that the structlog processor automatically masks PII
(emails) and redacts sensitive data (passwords, tokens) in logs.

Story 3.15.5: Plugin Architecture Foundation (PII protection enhancement)
"""

from mailreactor.utils.logging import _filter_sensitive_data, _mask_email


class TestEmailMasking:
    """Test email masking helper function."""

    def test_mask_email_standard(self):
        """Test masking standard email addresses."""
        assert _mask_email("user@example.com") == "***@example.com"
        assert _mask_email("john.doe@company.org") == "***@company.org"
        assert _mask_email("test+tag@domain.co.uk") == "***@domain.co.uk"

    def test_mask_email_invalid(self):
        """Test masking invalid email formats."""
        assert _mask_email("invalid") == "***"
        assert _mask_email("no-at-sign") == "***"
        assert _mask_email("") == "***"

    def test_mask_email_multiple_at_signs(self):
        """Test masking malformed emails with multiple @ signs."""
        # Only splits on first @, rest is treated as domain
        result = _mask_email("user@domain@extra")
        assert result == "***"  # Split gives >2 parts, so fallback

    def test_mask_email_non_string(self):
        """Test masking non-string values."""
        assert _mask_email(123) == "123"
        assert _mask_email(None) == "None"


class TestSensitiveDataFilter:
    """Test structlog processor for PII/sensitive data filtering."""

    def test_redact_password_fields(self):
        """Test automatic redaction of password fields."""
        event_dict = {
            "event": "login",
            "password": "secret123",  # pragma: allowlist secret
            "username": "testuser",
        }

        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        assert result["password"] == "[REDACTED]"
        assert result["username"] == "testuser"  # Not sensitive

    def test_redact_multiple_sensitive_fields(self):
        """Test redaction of all sensitive field types."""
        event_dict = {
            "event": "auth",
            "password": "secret",  # pragma: allowlist secret
            "api_key": "key123",  # pragma: allowlist secret
            "auth_token": "token456",  # pragma: allowlist secret
            "secret": "shh",  # pragma: allowlist secret
            "token": "bearer789",  # pragma: allowlist secret
            "authorization": "Bearer xyz",
        }

        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        # All should be redacted
        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert result["auth_token"] == "[REDACTED]"
        assert result["secret"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["authorization"] == "[REDACTED]"

    def test_mask_email_fields(self):
        """Test automatic masking of email PII."""
        event_dict = {
            "event": "email_sent",
            "email": "user@example.com",
            "recipient": "recipient@domain.org",
            "sender": "sender@company.com",
        }

        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        # Emails should be masked
        assert result["email"] == "***@example.com"
        assert result["recipient"] == "***@domain.org"
        assert result["sender"] == "***@company.com"

    def test_case_insensitive_field_matching(self):
        """Test that field matching is case-insensitive."""
        event_dict = {
            "Password": "secret",  # pragma: allowlist secret
            "EMAIL": "user@example.com",
            "Api_Key": "key123",  # pragma: allowlist secret
        }

        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        assert result["Password"] == "[REDACTED]"
        assert result["EMAIL"] == "***@example.com"
        assert result["Api_Key"] == "[REDACTED]"

    def test_non_pii_fields_unchanged(self):
        """Test that non-PII/non-sensitive fields are not modified."""
        event_dict = {
            "event": "test",
            "user_id": "12345",
            "imap_host": "imap.example.com",
            "port": 993,
            "ssl": True,
        }

        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        # All should remain unchanged
        assert result["event"] == "test"
        assert result["user_id"] == "12345"
        assert result["imap_host"] == "imap.example.com"
        assert result["port"] == 993
        assert result["ssl"] is True

    def test_mixed_sensitive_and_safe_fields(self):
        """Test filtering mixed event dict with both sensitive and safe fields."""
        event_dict = {
            "event": "account_configured",
            "email": "user@example.com",
            "imap_host": "imap.gmail.com",
            "smtp_host": "smtp.gmail.com",
            "password": "secret",  # pragma: allowlist secret
        }

        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        assert result["event"] == "account_configured"
        assert result["email"] == "***@example.com"
        assert result["imap_host"] == "imap.gmail.com"
        assert result["smtp_host"] == "smtp.gmail.com"
        assert result["password"] == "[REDACTED]"

    def test_email_field_with_non_string_value(self):
        """Test that non-string values in email fields don't crash."""
        event_dict = {
            "email": None,  # Could happen with optional fields
            "recipient": 123,  # Malformed data
        }

        # Should not raise exception
        result = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        # Non-string values are left unchanged (only strings are masked)
        assert result["email"] is None
        assert result["recipient"] == 123

    def test_integration_with_structlog(self):
        """Test integration with structlog capturing logger."""
        # Manually apply processor (simulating structlog pipeline)
        event_dict = {
            "event": "test_event",
            "email": "user@example.com",
            "password": "secret123",  # pragma: allowlist secret
            "safe_field": "public_data",
        }

        filtered = _filter_sensitive_data(None, "info", event_dict)  # type: ignore

        # Verify filtering
        assert filtered["email"] == "***@example.com"
        assert filtered["password"] == "[REDACTED]"
        assert filtered["safe_field"] == "public_data"
