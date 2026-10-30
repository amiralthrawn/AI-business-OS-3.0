import uuid
from typing import Callable

from sqlalchemy.orm import Session

from app.core.entities import (
    CommercialDocument,
    Communication,
    Company,
    Customer,
    Opportunity,
    Product,
    Risk,
    Supplier,
    Task,
)
from app.core.entities.event_log import EventLogEntry
from app.core.events.bus import EventHandler
from app.core.events.business_event import BusinessEvent
from app.core.events.subjects import infer_subject
from app.core.events.tenant import publishing_company

_SUBJECT_MODELS = {
    "commercial_document": CommercialDocument,
    "communication": Communication,
    "customer": Customer,
    "opportunity": Opportunity,
    "product": Product,
    "risk": Risk,
    "supplier": Supplier,
    "task": Task,
}


def _event_company(session: Session, subject_type: str | None, subject_id: uuid.UUID | None) -> uuid.UUID | None:
    """The company publishing the event (a signed-in request, V3); else the
    company of the object it is about; else the only company there is (seed
    scripts, the legacy single-company mode). Unknown otherwise."""

    company_id = publishing_company()
    if company_id is not None:
        return company_id
    model = _SUBJECT_MODELS.get(subject_type or "")
    if model is not None and subject_id is not None:
        subject = session.get(model, subject_id)
        if subject is not None:
            return subject.company_id
    companies = session.query(Company.id).limit(2).all()
    return companies[0][0] if len(companies) == 1 else None


def make_event_log_handler(session_factory: Callable[[], Session]) -> EventHandler:
    """Builds a handler that persists every event it receives into the Event Log.
    Meant to be subscribed to the bus's wildcard event type, so the log is just
    another consumer of the bus rather than logic baked into the bus itself.

    Takes a session factory rather than a live Session: the bus this handler is
    attached to is shared for the whole application lifetime, so the handler
    must open and close its own short-lived session on every call instead of
    depending on whichever request happened to be running when it was wired up.
    """

    def handle(event: BusinessEvent) -> None:
        subject_type, subject_id = infer_subject(event.payload)
        session = session_factory()
        try:
            session.add(
                EventLogEntry(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    payload=event.payload,
                    source=event.source,
                    correlation_id=event.correlation_id,
                    occurred_at=event.occurred_at,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    company_id=_event_company(session, subject_type, subject_id),
                )
            )
            session.commit()
        finally:
            session.close()

    return handle
