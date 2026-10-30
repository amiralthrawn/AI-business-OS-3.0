from app.core.events.bus import EventBus
from app.event_bus import event_bus


def get_event_bus() -> EventBus:
    return event_bus
