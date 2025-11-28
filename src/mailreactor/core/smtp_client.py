"""Async SMTP client for sending emails.

Uses aiosmtplib (MIT licensed, native async) for email sending.
This module is TRANSPORT-AGNOSTIC - zero FastAPI dependencies.
"""

from dataclasses import dataclass
from typing import List, Optional
from email.message import EmailMessage

try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None

from mailreactor.core.events import EventEmitter, EventHandler, MessageSentEvent


@dataclass
class SMTPConfig:
    """Configuration for SMTP connection."""

    host: str
    port: int = 587
    use_tls: bool = True
    username: str | None = None
    password: str | None = None


class AsyncSMTPClient:
    """Async SMTP client for sending emails.

    Uses aiosmtplib (MIT licensed, native async) - no executor needed.

    Usage (Library Mode):
        client = AsyncSMTPClient(
            host="smtp.gmail.com",
            port=587,
            use_tls=True
        )

        @client.on_message_sent
        async def handle_sent(event):
            print(f"Sent: {event.data['subject']}")

        await client.send_message(
            from_addr="sender@example.com",
            to_addrs=["recipient@example.com"],
            subject="Hello",
            body="Test message"
        )

    Usage (API Mode):
        # Same client, called from FastAPI endpoints
    """

    def __init__(
        self,
        host: str,
        port: int = 587,
        use_tls: bool = True,
        username: str | None = None,
        password: str | None = None,
    ):
        """Initialize AsyncSMTPClient.

        Args:
            host: SMTP server hostname
            port: SMTP server port (default: 587 for STARTTLS)
            use_tls: Use STARTTLS (default: True)
            username: SMTP username (optional, for authentication)
            password: SMTP password (optional, for authentication)
        """
        if aiosmtplib is None:
            raise ImportError(
                "aiosmtplib is required for SMTP functionality. "
                "Install with: pip install aiosmtplib"
            )

        self.config = SMTPConfig(
            host=host, port=port, use_tls=use_tls, username=username, password=password
        )
        self.events = EventEmitter()

    def on_message_sent(self, handler: EventHandler) -> EventHandler:
        """Decorator to register message sent handler.

        Example:
            @client.on_message_sent
            async def my_handler(event: MessageSentEvent):
                print(f"Sent: {event.data['subject']}")
        """
        return self.events.on("message.sent")(handler)

    async def send_message(
        self,
        from_addr: str,
        to_addrs: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc_addrs: Optional[List[str]] = None,
        bcc_addrs: Optional[List[str]] = None,
    ) -> None:
        """Send an email message.

        Args:
            from_addr: Sender email address
            to_addrs: List of recipient email addresses
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML email body
            cc_addrs: Optional CC recipients
            bcc_addrs: Optional BCC recipients
        """
        # Create email message
        message = EmailMessage()
        message["From"] = from_addr
        message["To"] = ", ".join(to_addrs)
        message["Subject"] = subject

        if cc_addrs:
            message["Cc"] = ", ".join(cc_addrs)

        # Set body
        message.set_content(body)

        if html_body:
            message.add_alternative(html_body, subtype="html")

        # Combine all recipients
        all_recipients = to_addrs.copy()
        if cc_addrs:
            all_recipients.extend(cc_addrs)
        if bcc_addrs:
            all_recipients.extend(bcc_addrs)

        # Send via SMTP
        async with aiosmtplib.SMTP(
            hostname=self.config.host, port=self.config.port, use_tls=self.config.use_tls
        ) as smtp:
            if self.config.username and self.config.password:
                await smtp.login(self.config.username, self.config.password)

            await smtp.send_message(message)

        # Emit event
        event_data = {
            "from": from_addr,
            "to": to_addrs,
            "subject": subject,
            "timestamp": message["Date"] if "Date" in message else None,
        }
        await self.events.emit(MessageSentEvent(event_data))

    async def send_raw(self, from_addr: str, to_addrs: List[str], message: str) -> None:
        """Send a raw RFC822 formatted email message.

        Args:
            from_addr: Sender email address
            to_addrs: List of recipient email addresses
            message: Raw RFC822 formatted message
        """
        async with aiosmtplib.SMTP(
            hostname=self.config.host, port=self.config.port, use_tls=self.config.use_tls
        ) as smtp:
            if self.config.username and self.config.password:
                await smtp.login(self.config.username, self.config.password)

            await smtp.sendmail(from_addr, to_addrs, message)

        # Emit event
        event_data = {
            "from": from_addr,
            "to": to_addrs,
            "raw": True,
        }
        await self.events.emit(MessageSentEvent(event_data))
