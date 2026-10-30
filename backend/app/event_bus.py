"""The application-lifetime Event Bus: one InProcessEventBus instance shared by
every request (and by scripts such as the seed), with every cross-cutting
handler -- Event Log, Intelligence's risk detector, Actions' task creator --
wired in once here rather than per request.

Domain code (Procurement, ...) only ever depends on the `EventBus` interface
and never imports this module directly; it receives whichever bus instance is
injected. Handlers registered here must manage their own DB session (opened
per call via a session factory) since the bus outlives any single request.
"""

from typing import Callable

from sqlalchemy.orm import Session

from app.actions.handlers import make_risk_created_handler
from app.core.events.bus import WILDCARD_EVENT_TYPE, EventBus, InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.database import SessionLocal
from app.domains.procurement.service import SUPPLIER_COST_INCREASED
from app.intelligence.risks.handlers import make_supplier_cost_increased_handler
from app.intelligence.risks.service import RISK_CREATED


def build_event_bus(session_factory: Callable[[], Session] = SessionLocal) -> EventBus:
    """Builds a fully-wired bus. Exposed as a function (rather than only the
    singleton below) so tests can rebuild the same wiring against an isolated
    session factory instead of the real application database."""

    bus = InProcessEventBus()
    bus.subscribe(WILDCARD_EVENT_TYPE, make_event_log_handler(session_factory))
    bus.subscribe(SUPPLIER_COST_INCREASED, make_supplier_cost_increased_handler(session_factory, bus))
    bus.subscribe(RISK_CREATED, make_risk_created_handler(session_factory, bus))
    return bus


event_bus: EventBus = build_event_bus()
