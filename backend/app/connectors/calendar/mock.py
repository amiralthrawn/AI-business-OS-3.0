"""MockCalendarProvider: a realistic, static in-memory calendar. Attendee
emails deliberately match the same external identities app.connectors.email's
mock mailbox uses (Northline Steel, BrightWorks Ltd, Thornfield Industries)
so a Contact resolved from one connector is recognizable across the other --
see brain/connectors.md.

No business logic here -- just data, the CalendarProvider methods, and plain
interval arithmetic for availability (never a scheduling recommendation).
"""

from datetime import datetime, timedelta, timezone

from app.connectors.calendar.base import CalendarProvider
from app.connectors.models import ExternalCalendarEvent


def _seed_events(now: datetime) -> list[ExternalCalendarEvent]:
    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return [
        # A meeting that already happened -- a supplier check-in.
        ExternalCalendarEvent(
            external_id="calendar_001",
            title="Pacific Components quarterly review",
            start=today_9am - timedelta(days=1),
            end=today_9am - timedelta(days=1) + timedelta(hours=1),
            attendees=["contracts@pacificcomponents.example", "procurement@acme.example"],
            location="Video call",
            status="confirmed",
        ),
        # Internal meeting.
        ExternalCalendarEvent(
            external_id="calendar_002",
            title="Weekly ops sync",
            start=today_9am + timedelta(days=1),
            end=today_9am + timedelta(days=1, minutes=30),
            attendees=["ops@acme.example", "purchasing@acme.example"],
            status="confirmed",
        ),
        # Supplier appointment -- overlaps with calendar_004 below (a real conflict).
        ExternalCalendarEvent(
            external_id="calendar_003",
            title="Northline Steel pricing call",
            start=today_9am + timedelta(days=2, hours=1),
            end=today_9am + timedelta(days=2, hours=2),
            attendees=["procurement@northlinesteel.com", "purchasing@acme.example"],
            location="Video call",
            status="confirmed",
        ),
        # Customer appointment -- deliberately overlaps calendar_003.
        ExternalCalendarEvent(
            external_id="calendar_004",
            title="BrightWorks delivery follow-up",
            start=today_9am + timedelta(days=2, hours=1, minutes=30),
            end=today_9am + timedelta(days=2, hours=2),
            attendees=["ops@brightworks.co.uk", "support@acme.example"],
            location="Phone",
            status="confirmed",
        ),
        # Prospect appointment.
        ExternalCalendarEvent(
            external_id="calendar_005",
            title="Thornfield Industries product demo",
            start=today_9am + timedelta(days=3, hours=5),
            end=today_9am + timedelta(days=3, hours=6),
            attendees=["sales@thornfieldindustries.example", "sales@acme.example"],
            location="Video call",
            status="tentative",
        ),
        # A free day (calendar_006 leaves plenty of open slots around it).
        ExternalCalendarEvent(
            external_id="calendar_006",
            title="Internal planning",
            start=today_9am + timedelta(days=4),
            end=today_9am + timedelta(days=4, hours=1),
            attendees=["ops@acme.example"],
            status="confirmed",
        ),
    ]


class MockCalendarProvider(CalendarProvider):
    def __init__(self, now: datetime | None = None) -> None:
        self._events: list[ExternalCalendarEvent] = _seed_events(now or datetime.now(timezone.utc))

    def list_events(self, start: datetime, end: datetime) -> list[ExternalCalendarEvent]:
        return [e for e in self._events if start <= e.start < end]

    def get_event(self, external_id: str) -> ExternalCalendarEvent | None:
        return next((e for e in self._events if e.external_id == external_id), None)

    def get_availability(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        confirmed = sorted(
            (e for e in self.list_events(start, end) if e.status != "cancelled"), key=lambda e: e.start
        )
        slots: list[tuple[datetime, datetime]] = []
        cursor = start
        for event in confirmed:
            if event.start > cursor:
                slots.append((cursor, event.start))
            cursor = max(cursor, event.end)
        if cursor < end:
            slots.append((cursor, end))
        return slots

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
        event = ExternalCalendarEvent(
            external_id=f"calendar_{len(self._events) + 1:03d}",
            title=title,
            start=start,
            end=end,
            attendees=attendees,
            description=description,
            location=location,
            status="confirmed",
        )
        self._events.append(event)
        return event

    def update_event(self, external_id: str, **changes) -> ExternalCalendarEvent:
        event = self.get_event(external_id)
        if event is None:
            raise KeyError(f"Unknown calendar event: '{external_id}'")
        updated = ExternalCalendarEvent(**{**event.__dict__, **changes})
        self._events[self._events.index(event)] = updated
        return updated

    def cancel_event(self, external_id: str) -> ExternalCalendarEvent:
        return self.update_event(external_id, status="cancelled")
