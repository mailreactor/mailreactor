"""Custom exception hierarchy for Mail Reactor.

All exceptions inherit from MailReactorException which includes HTTP status code
mapping for consistent error responses from FastAPI exception handlers.

Exception Hierarchy:
- MailReactorException (base)
  - AccountError (400): Account-related errors
  - ConnectionError (503): IMAP/SMTP connection failures
  - AuthenticationError (401): Authentication/authorization failures
  - MessageError (400): Email message processing errors
  - StateError (500): State management errors
"""


class MailReactorException(Exception):
    """Base exception for all Mail Reactor errors.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code for API error responses

    Examples:
        >>> raise MailReactorException("Something went wrong", status_code=500)
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize exception with message and HTTP status code.

        Args:
            message: Human-readable error description
            status_code: HTTP status code (default: 500 Internal Server Error)
        """
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AccountError(MailReactorException):
    """Account-related errors (e.g., account not found, invalid configuration).

    HTTP Status: 400 Bad Request

    Examples:
        >>> raise AccountError("Account 'user@example.com' not found")
    """

    def __init__(self, message: str) -> None:
        """Initialize account error with 400 status code.

        Args:
            message: Description of the account error
        """
        super().__init__(message, status_code=400)


class ConnectionError(MailReactorException):
    """IMAP/SMTP connection failures (e.g., host unreachable, timeout).

    HTTP Status: 503 Service Unavailable

    Examples:
        >>> raise ConnectionError("Failed to connect to imap.gmail.com:993")
    """

    def __init__(self, message: str) -> None:
        """Initialize connection error with 503 status code.

        Args:
            message: Description of the connection failure
        """
        super().__init__(message, status_code=503)


class AuthenticationError(MailReactorException):
    """Authentication/authorization failures (e.g., invalid credentials, expired token).

    HTTP Status: 401 Unauthorized

    Examples:
        >>> raise AuthenticationError("Invalid password for user@example.com")
    """

    def __init__(self, message: str) -> None:
        """Initialize authentication error with 401 status code.

        Args:
            message: Description of the authentication failure
        """
        super().__init__(message, status_code=401)


class MessageError(MailReactorException):
    """Email message processing errors (e.g., invalid format, missing required fields).

    HTTP Status: 400 Bad Request

    Examples:
        >>> raise MessageError("Email missing required 'to' field")
    """

    def __init__(self, message: str) -> None:
        """Initialize message error with 400 status code.

        Args:
            message: Description of the message processing error
        """
        super().__init__(message, status_code=400)


class StateError(MailReactorException):
    """State management errors (e.g., failed to save state, corrupted state data).

    HTTP Status: 500 Internal Server Error

    Examples:
        >>> raise StateError("Failed to serialize account state to IMAP folder")
    """

    def __init__(self, message: str) -> None:
        """Initialize state error with 500 status code.

        Args:
            message: Description of the state management error
        """
        super().__init__(message, status_code=500)
