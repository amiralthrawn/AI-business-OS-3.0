from typing import Callable

from sqlalchemy.orm import Session

from app.actions.service import ActionsService
from app.core.events.bus import EventBus, EventHandler
from app.core.events.business_event import BusinessEvent


def make_risk_created_handler(session_factory: Callable[[], Session], event_bus: EventBus) -> EventHandler:
    """Builds the Event Bus handler for RiskCreated. Opens its own short-lived
    session per call, same reasoning as the Event Log and Risk detection
    handlers: this handler is wired into an application-lifetime bus, not a
    single request."""

    def handle(event: BusinessEvent) -> None:
        session = session_factory()
        try:
            ActionsService(session, event_bus).create_task_from_risk_created(event)
        finally:
            session.close()

    return handle
