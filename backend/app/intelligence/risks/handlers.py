from typing import Callable

from sqlalchemy.orm import Session

from app.core.events.bus import EventBus, EventHandler
from app.core.events.business_event import BusinessEvent
from app.intelligence.risks.service import RiskDetectionService


def make_supplier_cost_increased_handler(
    session_factory: Callable[[], Session], event_bus: EventBus
) -> EventHandler:
    """Builds the Event Bus handler for SupplierCostIncreased. Opens its own
    short-lived session per call, same reasoning as the Event Log handler: this
    handler is wired into an application-lifetime bus, not a single request."""

    def handle(event: BusinessEvent) -> None:
        session = session_factory()
        try:
            RiskDetectionService(session, event_bus).evaluate_supplier_cost_increase(event)
        finally:
            session.close()

    return handle
