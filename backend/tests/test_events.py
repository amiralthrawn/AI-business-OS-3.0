import pytest

from app.core.entities import EventLogEntry
from app.core.events.business_event import BusinessEvent
from app.core.events.log_handler import make_event_log_handler


def test_handler_receives_published_event(event_bus):
    received = []
    event_bus.subscribe("supplier.cost_increased", received.append)

    event = BusinessEvent(event_type="supplier.cost_increased", payload={"supplier_id": "abc"}, source="test")
    event_bus.publish(event)

    assert len(received) == 1
    assert received[0].event_id == event.event_id


def test_event_log_persists_published_event(db_session, session_factory, event_bus):
    event_bus.subscribe("*", make_event_log_handler(session_factory))

    event = BusinessEvent(event_type="supplier.cost_increased", payload={"delta_pct": 0.11}, source="test")
    event_bus.publish(event)

    entry = db_session.query(EventLogEntry).filter_by(event_id=event.event_id).one()
    assert entry.event_type == "supplier.cost_increased"
    assert entry.source == "test"
    assert entry.correlation_id == event.correlation_id


def test_bus_does_not_redeliver_the_same_event_twice(event_bus):
    calls = []
    event_bus.subscribe("x", calls.append)
    event = BusinessEvent(event_type="x", payload={}, source="test")

    event_bus.publish(event)
    event_bus.publish(event)

    assert len(calls) == 1


def test_bus_detects_propagation_loop(event_bus):
    def handler(_event: BusinessEvent) -> None:
        event_bus.publish(BusinessEvent(event_type="loop", payload={}, source="handler"))

    event_bus.subscribe("loop", handler)

    with pytest.raises(RuntimeError):
        event_bus.publish(BusinessEvent(event_type="loop", payload={}, source="test"))
