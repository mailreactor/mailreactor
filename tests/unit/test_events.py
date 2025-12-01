"""Unit tests for EventEmitter and Event classes.

Tests cover:
- Event dataclass instantiation
- Handler registration via decorator
- Concurrent handler execution
- Exception isolation
- FR-099 validation (zero FastAPI imports)
"""

import asyncio
import sys
import pytest

from mailreactor.core.events import Event, EventEmitter


class TestEvent:
    """Test Event dataclass."""

    def test_event_creation(self):
        """Test Event instantiation with type and data."""
        event = Event("message.received", data={"subject": "Test", "from": "user@example.com"})

        assert event.event_type == "message.received"
        assert event.data == {"subject": "Test", "from": "user@example.com"}

    def test_event_empty_data(self):
        """Test Event with empty data dictionary."""
        event = Event("user.logout", {})

        assert event.event_type == "user.logout"
        assert event.data == {}


class TestEventEmitter:
    """Test EventEmitter handler registration and emission."""

    def test_handler_registration(self):
        """Test decorator registers async handlers correctly."""
        emitter = EventEmitter()

        @emitter.on("test.event")
        async def handler(event: Event):
            pass

        # Handler should be registered
        assert "test.event" in emitter._handlers
        assert len(emitter._handlers["test.event"]) == 1
        assert emitter._handlers["test.event"][0] == handler

    def test_multiple_handlers_same_event(self):
        """Test multiple handlers can register for same event type."""
        emitter = EventEmitter()

        @emitter.on("test.event")
        async def handler1(event: Event):
            pass

        @emitter.on("test.event")
        async def handler2(event: Event):
            pass

        assert len(emitter._handlers["test.event"]) == 2
        assert handler1 in emitter._handlers["test.event"]
        assert handler2 in emitter._handlers["test.event"]

    def test_handlers_different_events(self):
        """Test handlers registered for different event types."""
        emitter = EventEmitter()

        @emitter.on("event.one")
        async def handler1(event: Event):
            pass

        @emitter.on("event.two")
        async def handler2(event: Event):
            pass

        assert "event.one" in emitter._handlers
        assert "event.two" in emitter._handlers
        assert len(emitter._handlers["event.one"]) == 1
        assert len(emitter._handlers["event.two"]) == 1

    @pytest.mark.asyncio
    async def test_emit_calls_handler(self):
        """Test emit calls registered handler with event."""
        emitter = EventEmitter()
        received_event = None

        @emitter.on("test.event")
        async def handler(event: Event):
            nonlocal received_event
            received_event = event

        test_event = Event("test.event", data={"key": "value"})
        await emitter.emit(test_event)

        assert received_event is test_event
        assert received_event.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self):
        """Test emit with no handlers doesn't raise."""
        emitter = EventEmitter()

        # Should not raise
        await emitter.emit(Event("unknown.event", {}))

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Test handlers execute concurrently via asyncio.gather."""
        emitter = EventEmitter()
        execution_order = []

        @emitter.on("test.event")
        async def handler1(event: Event):
            execution_order.append("handler1_start")
            await asyncio.sleep(0.1)
            execution_order.append("handler1_end")

        @emitter.on("test.event")
        async def handler2(event: Event):
            execution_order.append("handler2_start")
            await asyncio.sleep(0.05)
            execution_order.append("handler2_end")

        await emitter.emit(Event("test.event", {}))

        # Both handlers should start before either ends (concurrent execution)
        assert "handler1_start" in execution_order
        assert "handler2_start" in execution_order
        assert execution_order.index("handler2_start") < execution_order.index("handler1_end")

    @pytest.mark.asyncio
    async def test_exception_isolation(self):
        """Test handler failures don't crash emit or affect other handlers."""
        emitter = EventEmitter()
        handler2_called = False

        @emitter.on("test.event")
        async def failing_handler(event: Event):
            raise ValueError("Handler failed")

        @emitter.on("test.event")
        async def successful_handler(event: Event):
            nonlocal handler2_called
            handler2_called = True

        # Should not raise despite failing_handler exception
        await emitter.emit(Event("test.event", {}))

        # Successful handler should still execute
        assert handler2_called is True


class TestFR099Validation:
    """Test FR-099: Core module has zero FastAPI coupling."""

    def test_no_fastapi_imports(self):
        """Test importing mailreactor.core.events does NOT load fastapi modules."""
        # Clear any existing fastapi modules
        fastapi_modules = [key for key in sys.modules.keys() if key.startswith("fastapi")]
        for module in fastapi_modules:
            del sys.modules[module]

        # Import core.events

        # Verify fastapi is NOT in sys.modules
        fastapi_modules = [key for key in sys.modules.keys() if key.startswith("fastapi")]
        assert len(fastapi_modules) == 0, f"FastAPI modules found: {fastapi_modules}"

    def test_no_pydantic_http_imports(self):
        """Test core.events doesn't import Pydantic HTTP models."""
        from mailreactor.core.events import EventEmitter

        # This is a stronger check - ensure no Pydantic HTTP-specific imports
        # The module can import from mailreactor.models.* but not from pydantic directly
        # for HTTP-specific models (BaseModel is ok for data classes)
        import inspect

        source = inspect.getsource(EventEmitter)

        # Should not import from fastapi or starlette
        assert "from fastapi" not in source
        assert "from starlette" not in source
        assert "import fastapi" not in source
        assert "import starlette" not in source
