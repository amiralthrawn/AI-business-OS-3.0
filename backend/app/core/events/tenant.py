"""Which company an event belongs to (V3).

The bus is shared by every company, and events carry no company of their own
(42 publishers, none of which needed one while the product had a single
company). The Event Log still has to know it, or one company's decisions and
timeline would show up in another's Home.

`TenantEventBus` wraps the shared bus for one signed-in request: while it
publishes, the request's company is held in a context variable. Handlers run
synchronously in the publishing call stack, so every event published during
that call -- including the ones handlers publish in reaction, through the
shared bus -- is logged for that company (app.core.events.log_handler).
"""

import uuid
from contextvars import ContextVar

from app.core.events.bus import EventBus, EventHandler
from app.core.events.business_event import BusinessEvent

_publishing_company: ContextVar[uuid.UUID | None] = ContextVar("publishing_company", default=None)


def publishing_company() -> uuid.UUID | None:
    return _publishing_company.get()


class TenantEventBus(EventBus):
    def __init__(self, inner: EventBus, company_id: uuid.UUID) -> None:
        self._inner = inner
        self._company_id = company_id

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._inner.subscribe(event_type, handler)

    def publish(self, event: BusinessEvent) -> None:
        token = _publishing_company.set(self._company_id)
        try:
            self._inner.publish(event)
        finally:
            _publishing_company.reset(token)
