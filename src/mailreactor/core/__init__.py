"""Core business logic - transport-agnostic email operations.

This module contains all core functionality that can be used independently
of FastAPI or any HTTP server. Supports both library mode and API mode.
"""

from mailreactor.core.events import EventEmitter, Event, MessageReceivedEvent, MessageSentEvent
from mailreactor.core.imap_client import AsyncIMAPClient, IMAPConfig
from mailreactor.core.smtp_client import AsyncSMTPClient, SMTPConfig

__all__ = [
    "EventEmitter",
    "Event",
    "MessageReceivedEvent",
    "MessageSentEvent",
    "AsyncIMAPClient",
    "IMAPConfig",
    "AsyncSMTPClient",
    "SMTPConfig",
]
