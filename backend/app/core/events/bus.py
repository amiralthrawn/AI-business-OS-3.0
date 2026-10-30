import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Callable

from app.core.events.business_event import BusinessEvent

EventHandler = Callable[[BusinessEvent], None]

WILDCARD_EVENT_TYPE = "*"


class EventBus(ABC):
    """Interface that publishers and handlers depend on. Business/domain code must
    only ever type-hint against this class, never against a concrete
    implementation, so the in-process bus can later be swapped for a distributed
    one (e.g. Redis Streams) without touching any publisher or handler."""

    @abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for `event_type`, or for every event type when
        `event_type` is `WILDCARD_EVENT_TYPE` (used by the Event Log handler)."""

    @abstractmethod
    def publish(self, event: BusinessEvent) -> None: ...


class InProcessEventBus(EventBus):
    """Synchronous, in-memory implementation for the MVP. Handlers run in the
    publishing call stack, in subscription order. Not durable across process
    restarts and not shared across processes -- acceptable for a single-process
    modular monolith, and the first thing to replace if that ever changes."""

    MAX_PROPAGATION_DEPTH = 10

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._processed_event_ids: set[uuid.UUID] = set()
        self._depth = 0

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: BusinessEvent) -> None:
        # Minimal protection against the same event object being delivered twice.
        if event.event_id in self._processed_event_ids:
            return
        self._processed_event_ids.add(event.event_id)

        # Minimal protection against a handler re-publishing in a cycle: since
        # this bus is synchronous, an unbounded loop would otherwise recurse
        # through publish() until the process crashes with a stack overflow.
        if self._depth >= self.MAX_PROPAGATION_DEPTH:
            raise RuntimeError(
                f"Event propagation depth exceeded {self.MAX_PROPAGATION_DEPTH} while "
                f"publishing '{event.event_type}' (correlation_id={event.correlation_id}); "
                "a handler is likely publishing events in a loop."
            )

        handlers = list(self._handlers.get(event.event_type, [])) + list(
            self._handlers.get(WILDCARD_EVENT_TYPE, [])
        )

        self._depth += 1
        try:
            for handler in handlers:
                handler(event)
        finally:
            self._depth -= 1
