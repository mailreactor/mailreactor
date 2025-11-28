"""Transport-agnostic event system for Mail Reactor.

Supports both library mode (Python async callbacks) and API mode (webhooks).
This module has ZERO dependencies on FastAPI or any HTTP framework.
"""

import asyncio
from typing import Any, Awaitable, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    """Base event class for all Mail Reactor events."""

    event_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Event(type={self.event_type}, timestamp={self.timestamp}, data_keys={list(self.data.keys())})"


@dataclass
class MessageReceivedEvent(Event):
    """Event emitted when a new message is received via IMAP."""

    def __init__(self, message_data: Dict[str, Any]):
        super().__init__(event_type="message.received", data=message_data)


@dataclass
class MessageSentEvent(Event):
    """Event emitted when a message is sent via SMTP."""

    def __init__(self, message_data: Dict[str, Any]):
        super().__init__(event_type="message.sent", data=message_data)


EventHandler = Callable[[Event], Awaitable[None]]


class EventEmitter:
    """Transport-agnostic event emitter.

    Supports async handler registration and concurrent event dispatch.
    Handlers are executed concurrently using asyncio.gather().

    Usage (Library Mode):
        emitter = EventEmitter()

        @emitter.on("message.received")
        async def handle_message(event: Event):
            print(f"New message: {event.data}")

        await emitter.emit(Event("message.received", data={"subject": "Hello"}))

    Usage (API Mode):
        # Webhook handler would subscribe to events and POST to URLs
        # This is implemented separately in api/ module
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = {}

    def on(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator to register an async event handler.

        Args:
            event_type: The type of event to listen for (e.g., "message.received")

        Returns:
            Decorator function that registers the handler

        Example:
            @emitter.on("message.received")
            async def my_handler(event: Event):
                print(event.data)
        """

        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler

        return decorator

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The type of event to listen for
            handler: Async callable that receives Event objects
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type.

        Args:
            event_type: The type of event
            handler: The handler to remove
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass  # Handler wasn't subscribed

    async def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers.

        Handlers are executed concurrently. If any handler raises an exception,
        it's logged but doesn't prevent other handlers from executing.

        Args:
            event: The event to emit
        """
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        # Execute all handlers concurrently
        results = await asyncio.gather(
            *[self._safe_handle(handler, event) for handler in handlers],
            return_exceptions=True,
        )

        # Log any exceptions (in production, use structlog)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Handler {i} for {event.event_type} failed: {result}")

    async def _safe_handle(self, handler: EventHandler, event: Event) -> None:
        """Execute a handler with exception isolation.

        Args:
            handler: The async handler to execute
            event: The event to pass to the handler
        """
        try:
            await handler(event)
        except Exception as e:
            # Re-raise so gather can catch it
            raise e

    def handler_count(self, event_type: str) -> int:
        """Get the number of handlers registered for an event type.

        Args:
            event_type: The event type to check

        Returns:
            Number of registered handlers
        """
        return len(self._handlers.get(event_type, []))

    def clear_handlers(self, event_type: str | None = None) -> None:
        """Clear handlers for a specific event type or all handlers.

        Args:
            event_type: Optional event type to clear. If None, clears all handlers.
        """
        if event_type is None:
            self._handlers.clear()
        elif event_type in self._handlers:
            del self._handlers[event_type]
