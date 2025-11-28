"""Async IMAP client using executor pattern.

Wraps synchronous IMAPClient (BSD-3 license) with asyncio.run_in_executor()
to provide async interface without GPL-3 copyleft dependencies.

This module is TRANSPORT-AGNOSTIC - zero FastAPI dependencies.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, List
from dataclasses import dataclass

from imapclient import IMAPClient

from mailreactor.core.events import EventEmitter, EventHandler, MessageReceivedEvent


@dataclass
class IMAPConfig:
    """Configuration for IMAP connection."""

    host: str
    port: int = 993
    use_ssl: bool = True
    username: str | None = None
    password: str | None = None


class AsyncIMAPClient:
    """Async wrapper around synchronous IMAPClient using thread pool executor.

    This class demonstrates that core business logic works independently
    of FastAPI or any HTTP server. Can be used in library mode or API mode.

    Usage (Library Mode):
        client = AsyncIMAPClient(
            host="imap.gmail.com",
            port=993,
            use_ssl=True
        )

        @client.on_message_received
        async def handle_message(event):
            print(f"New message: {event.data}")

        await client.connect(username="user@gmail.com", password="app-password") #pragma: allowlist secret
        await client.start_monitoring(poll_interval=60)

    Usage (API Mode):
        # Same client code, called from FastAPI endpoints
        # Event handlers would trigger webhooks instead of callbacks
    """

    def __init__(
        self,
        host: str,
        port: int = 993,
        use_ssl: bool = True,
        max_workers: int = 4,
    ):
        """Initialize AsyncIMAPClient.

        Args:
            host: IMAP server hostname
            port: IMAP server port (default: 993 for SSL)
            use_ssl: Use SSL/TLS connection (default: True)
            max_workers: Thread pool size for executor (default: 4)
        """
        self.config = IMAPConfig(host=host, port=port, use_ssl=use_ssl)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._client: IMAPClient | None = None
        self._monitoring = False
        self.events = EventEmitter()

    def on_message_received(self, handler: EventHandler) -> EventHandler:
        """Decorator to register message received handler.

        Example:
            @client.on_message_received
            async def my_handler(event: MessageReceivedEvent):
                print(event.data["subject"])
        """
        return self.events.on("message.received")(handler)

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute synchronous IMAPClient method in thread pool.

        This is the key pattern that allows us to use sync IMAPClient
        in an async context without blocking the event loop.

        Args:
            func: Synchronous function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, partial(func, *args, **kwargs))

    async def connect(self, username: str, password: str) -> None:
        """Connect and authenticate to IMAP server.

        Args:
            username: IMAP username (usually email address)
            password: IMAP password or app-specific password
        """
        self.config.username = username
        self.config.password = password

        def _connect() -> IMAPClient:
            client = IMAPClient(
                host=self.config.host, port=self.config.port, ssl=self.config.use_ssl
            )
            client.login(username, password)
            return client

        self._client = await self._run_sync(_connect)

    async def disconnect(self) -> None:
        """Disconnect from IMAP server and cleanup resources."""
        self._monitoring = False
        if self._client:
            await self._run_sync(self._client.logout)
            self._client = None
        self._executor.shutdown(wait=True)

    async def select_folder(self, folder: str = "INBOX") -> Any:
        """Select a mailbox folder.

        Args:
            folder: Folder name (default: "INBOX")

        Returns:
            Folder metadata (message count, etc.)
        """
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._run_sync(self._client.select_folder, folder)

    async def search(self, criteria: str | List[str] = "ALL") -> List[int]:
        """Search for messages using IMAP SEARCH command.

        Args:
            criteria: IMAP search criteria (default: "ALL")
                     Examples: "UNSEEN", "FROM user@example.com", ["SINCE", "01-Jan-2024"]

        Returns:
            List of message UIDs matching criteria
        """
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        return await self._run_sync(self._client.search, criteria)  # type: ignore[no-any-return]

    async def fetch_messages(
        self, uids: List[int], data: List[str] | None = None
    ) -> Dict[int, Any]:
        """Fetch message data for given UIDs.

        Args:
            uids: List of message UIDs to fetch
            data: IMAP fetch items (default: ["ENVELOPE", "FLAGS", "RFC822.SIZE"])

        Returns:
            Dict mapping UID -> message data
        """
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        if data is None:
            data = ["ENVELOPE", "FLAGS", "RFC822.SIZE"]

        return await self._run_sync(self._client.fetch, uids, data)  # type: ignore[no-any-return]

    async def list_messages(
        self, folder: str = "INBOX", criteria: str | List[str] = "ALL", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """High-level method to list messages in a folder.

        Args:
            folder: Folder to list (default: "INBOX")
            criteria: Search criteria (default: "ALL")
            limit: Maximum messages to return (default: 100)

        Returns:
            List of message dictionaries
        """
        await self.select_folder(folder)
        uids = await self.search(criteria)

        # Limit results
        uids = uids[-limit:] if len(uids) > limit else uids

        if not uids:
            return []

        messages_data = await self.fetch_messages(uids)

        # Convert to simplified format
        result = []
        for uid, data in messages_data.items():
            envelope = data.get(b"ENVELOPE")
            result.append(
                {
                    "uid": uid,
                    "subject": envelope.subject.decode() if envelope and envelope.subject else "",
                    "from": str(envelope.from_[0]) if envelope and envelope.from_ else "",
                    "date": envelope.date if envelope else None,
                    "size": data.get(b"RFC822.SIZE", 0),
                    "flags": [
                        f.decode() if isinstance(f, bytes) else f for f in data.get(b"FLAGS", [])
                    ],
                }
            )

        return result

    async def start_monitoring(self, poll_interval: int = 60, folder: str = "INBOX") -> None:
        """Start monitoring mailbox for new messages.

        This demonstrates the event-driven pattern working with executor threads.
        New messages trigger event emission to async handlers.

        Args:
            poll_interval: Seconds between polls (default: 60)
            folder: Folder to monitor (default: "INBOX")
        """
        self._monitoring = True
        await self.select_folder(folder)

        last_seen_uid = 0
        uids = await self.search("ALL")
        if uids:
            last_seen_uid = max(uids)

        print(f"Monitoring {folder} every {poll_interval}s. Last UID: {last_seen_uid}")

        while self._monitoring:
            await asyncio.sleep(poll_interval)

            # Check for new messages
            uids = await self.search("ALL")
            if not uids:
                continue

            max_uid = max(uids)
            if max_uid > last_seen_uid:
                # New messages detected
                new_uids = [uid for uid in uids if uid > last_seen_uid]
                messages = await self.fetch_messages(new_uids, ["ENVELOPE", "FLAGS"])

                # Emit events for each new message
                for uid, data in messages.items():
                    envelope = data.get(b"ENVELOPE")
                    event_data = {
                        "uid": uid,
                        "subject": envelope.subject.decode()
                        if envelope and envelope.subject
                        else "",
                        "from": str(envelope.from_[0]) if envelope and envelope.from_ else "",
                        "date": str(envelope.date) if envelope else None,
                    }
                    await self.events.emit(MessageReceivedEvent(event_data))

                last_seen_uid = max_uid

    def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._monitoring = False
