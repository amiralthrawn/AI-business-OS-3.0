from fastapi import Depends

from app.access.deps import CurrentUser, get_current_user
from app.core.events.bus import EventBus
from app.core.events.tenant import TenantEventBus
from app.event_bus import event_bus


def get_event_bus(user: CurrentUser = Depends(get_current_user)) -> EventBus:
    # V3: a signed-in request publishes for its own company, so the Event Log
    # files every event (and its consequences) under that company.
    if user.profile is not None:
        return TenantEventBus(event_bus, user.profile.company_id)
    return event_bus
