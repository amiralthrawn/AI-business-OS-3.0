import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.access.deps import CurrentUser, get_current_user
from app.agenda import service
from app.core.entities import CalendarEvent, Company
from app.core.i18n import tx
from app.database import get_db

router = APIRouter(prefix="/calendar", tags=["calendar"])


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: str = "other"
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = True
    notes: str | None = Field(default=None, max_length=2000)


def _own(db: Session, event_id: uuid.UUID) -> CalendarEvent:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=tx("Événement introuvable", "Event not found"))
    return event


@router.get("")
def get_calendar(start: datetime, end: datetime, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> dict:
    if end <= start or end - start > timedelta(days=service.MAX_RANGE_DAYS):
        raise HTTPException(status_code=422, detail=tx("Période invalide (100 jours maximum).", "Invalid period (100 days maximum)."))
    return service.build_calendar(db, user, start, end)


@router.post("/events", status_code=201)
def create_event(payload: EventIn, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> dict:
    company = db.query(Company).first()
    if company is None:
        raise HTTPException(status_code=404, detail=tx("Aucune entreprise", "No company"))
    kind = payload.kind if payload.kind in service.MANUAL_KINDS else "other"
    event = CalendarEvent(company_id=company.id, title=payload.title.strip(), kind=kind, starts_at=payload.starts_at, ends_at=payload.ends_at,
                          all_day=payload.all_day, notes=payload.notes, created_by=user.profile.id if user.profile else None)
    db.add(event)
    db.commit()
    return {"id": str(event.id)}


@router.put("/events/{event_id}")
def update_event(event_id: uuid.UUID, payload: EventIn, db: Session = Depends(get_db), _user: CurrentUser = Depends(get_current_user)) -> dict:
    event = _own(db, event_id)
    event.title, event.starts_at, event.ends_at = payload.title.strip(), payload.starts_at, payload.ends_at
    event.all_day, event.notes = payload.all_day, payload.notes
    event.kind = payload.kind if payload.kind in service.MANUAL_KINDS else "other"
    db.commit()
    return {"id": str(event.id)}


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: uuid.UUID, db: Session = Depends(get_db), _user: CurrentUser = Depends(get_current_user)) -> None:
    db.delete(_own(db, event_id))
    db.commit()
