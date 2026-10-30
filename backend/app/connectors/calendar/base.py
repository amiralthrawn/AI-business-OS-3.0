"""CalendarConnector interface: MockCalendarProvider today, a real
GoogleCalendarProvider/MicrosoftCalendarProvider later -- same interface,
swapped in app.connectors.registry without touching ingestion."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.connectors.models import ExternalCalendarEvent


class CalendarProvider(ABC):
    @abstractmethod
    def list_events(self, start: datetime, end: datetime) -> list[ExternalCalendarEvent]:
        """Every event whose start falls within [start, end)."""

    @abstractmethod
    def get_event(self, external_id: str) -> ExternalCalendarEvent | None:
        """A single event by the provider's own id, or `None`."""

    @abstractmethod
    def get_availability(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """Free (start, end) slots within the window, gaps between confirmed
        events -- plain scheduling arithmetic, not a recommendation."""

    @abstractmethod
    def create_event(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime,
        attendees: list[str],
        description: str | None = None,
        location: str | None = None,
    ) -> ExternalCalendarEvent:
        """Creates a new event. On the Mock Provider this only ever appends
        to its own in-memory calendar -- no real invite is ever sent."""

    @abstractmethod
    def update_event(self, external_id: str, **changes) -> ExternalCalendarEvent:
        """Updates an existing event's fields (title/start/end/description/location)."""

    @abstractmethod
    def cancel_event(self, external_id: str) -> ExternalCalendarEvent:
        """Marks an event cancelled (status="cancelled"); never deletes the record."""
