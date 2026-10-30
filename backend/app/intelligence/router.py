from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.events.bus import EventBus
from app.database import get_db
from app.dependencies import get_event_bus
from app.intelligence.monitoring import run_monitoring_sweep

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.post("/monitor")
def trigger_monitoring_sweep(
    db: Session = Depends(get_db), event_bus: EventBus = Depends(get_event_bus)
) -> dict:
    """Manually triggers the monitoring sweep (see app.intelligence.monitoring
    for why this isn't a scheduled job in the MVP)."""

    return run_monitoring_sweep(db, event_bus)
