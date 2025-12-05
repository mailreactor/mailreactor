"""Account and provider configuration models.

This module defines Pydantic models for email account management:
- ProviderConfig: Auto-detected IMAP/SMTP server settings
- IMAPConfig: IMAP server configuration with credentials
- SMTPConfig: SMTP server configuration with credentials
- MailAccount: Complete mail account with IMAP/SMTP connections

All models use Pydantic v2 for validation and serialization.
Password fields are marked with Field(exclude=True) to prevent exposure.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, Field


class ProviderConfig(BaseModel):
    """Email provider IMAP/SMTP configuration (auto-detected server settings).

    This model contains only server connection settings detected from providers.yaml
    or Mozilla Autoconfig. It does not include credentials.

    Attributes:
        provider_name: Provider identifier (e.g., "gmail", "outlook")
        imap_host: IMAP server hostname
        imap_port: IMAP server port (default 993 for SSL)
        imap_ssl: Use SSL for IMAP connection (default True)
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port (default 587 for STARTTLS)
        smtp_starttls: Use STARTTLS for SMTP connection (default True)
    """

    provider_name: str = Field(..., description="Provider identifier (gmail, outlook, etc.)")
    imap_host: str = Field(..., description="IMAP server hostname")
    imap_port: int = Field(993, description="IMAP server port", ge=1, le=65535)
    imap_ssl: bool = Field(True, description="Use SSL for IMAP connection")
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(587, description="SMTP server port", ge=1, le=65535)
    smtp_starttls: bool = Field(True, description="Use STARTTLS for SMTP connection")


class IMAPConfig(BaseModel):
    """IMAP server configuration and credentials.

    Contains all settings needed to establish an IMAP connection, including
    sensitive credentials. Password field is excluded from serialization.

    Attributes:
        host: IMAP server hostname
        port: IMAP server port (default 993 for SSL)
        ssl: Use SSL for IMAP connection (default True)
        username: IMAP username (usually email address, but can differ for shared mailboxes)
        password: IMAP password (excluded from serialization)
    """

    host: str = Field(..., description="IMAP server hostname", min_length=1)
    port: int = Field(993, description="IMAP server port", ge=1, le=65535)
    ssl: bool = Field(True, description="Use SSL for IMAP connection")
    username: str = Field(..., description="IMAP username (usually email)", min_length=1)
    password: str = Field(..., description="IMAP password", exclude=True, min_length=1)


class SMTPConfig(BaseModel):
    """SMTP server configuration and credentials.

    Contains all settings needed to establish an SMTP connection, including
    sensitive credentials. Password field is excluded from serialization.

    IMAP and SMTP credentials are kept separate to support advanced use cases:
    - Relay services (different SMTP credentials)
    - Shared mailboxes (different IMAP credentials)
    - OAuth scopes (separate permissions)

    Attributes:
        host: SMTP server hostname
        port: SMTP server port (default 587 for STARTTLS)
        starttls: Use STARTTLS for SMTP connection (default True)
        username: SMTP username (usually email address, but can differ for relay services)
        password: SMTP password (excluded from serialization)
    """

    host: str = Field(..., description="SMTP server hostname", min_length=1)
    port: int = Field(587, description="SMTP server port", ge=1, le=65535)
    starttls: bool = Field(True, description="Use STARTTLS for SMTP connection")
    username: str = Field(..., description="SMTP username (usually email)", min_length=1)
    password: str = Field(..., description="SMTP password", exclude=True, min_length=1)


class MailAccount(BaseModel):
    """Mail account with IMAP and SMTP connections.

    Represents a single email account with separate IMAP (receive) and SMTP (send)
    connection configurations. This is the complete account representation stored
    in the StateManager.

    Separate IMAP/SMTP configurations support advanced use cases:
    - Relay services (different SMTP provider)
    - Shared mailboxes (different IMAP credentials)
    - Corporate setups (separate incoming/outgoing servers)

    Attributes:
        account_id: Unique account identifier (generated: acc_{uuid4().hex[:8]})
        email: Primary email address (validated as EmailStr)
        imap: IMAP configuration with credentials
        smtp: SMTP configuration with credentials
        created_at: Account creation timestamp (UTC)
        connection_status: Connection status (pending, connected, error)
    """

    account_id: str = Field(..., description="Unique account identifier (acc_xxxxxxxx)")
    email: EmailStr = Field(..., description="Primary email address")
    imap: IMAPConfig = Field(..., description="IMAP server configuration and credentials")
    smtp: SMTPConfig = Field(..., description="SMTP server configuration and credentials")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Account creation timestamp (UTC, ISO 8601)",
    )
    connection_status: str = Field(
        "pending", description="Connection status: pending, connected, error"
    )
