"""Unit tests for custom exception hierarchy.

Tests cover:
- HTTP status code mapping
- Exception inheritance hierarchy
"""

from mailreactor.exceptions import (
    MailReactorException,
    AccountError,
    ConnectionError,
    AuthenticationError,
    MessageError,
    StateError,
)


class TestExceptionStatusCodes:
    """Test HTTP status code mapping for exceptions."""

    def test_base_exception_default_status(self):
        """Test MailReactorException defaults to 500."""
        exc = MailReactorException("Something went wrong")
        assert exc.status_code == 500
        assert str(exc) == "Something went wrong"

    def test_base_exception_custom_status(self):
        """Test MailReactorException accepts custom status code."""
        exc = MailReactorException("Bad request", status_code=400)
        assert exc.status_code == 400

    def test_all_exception_status_codes(self):
        """Test each exception type has correct HTTP status code."""
        test_cases = [
            (AccountError("test"), 400),
            (ConnectionError("test"), 503),
            (AuthenticationError("test"), 401),
            (MessageError("test"), 400),
            (StateError("test"), 500),
        ]

        for exc, expected_status in test_cases:
            assert exc.status_code == expected_status


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from MailReactorException."""
        exceptions = [
            AccountError("test"),
            ConnectionError("test"),
            AuthenticationError("test"),
            MessageError("test"),
            StateError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MailReactorException)
