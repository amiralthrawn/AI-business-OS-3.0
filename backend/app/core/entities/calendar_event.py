import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.entities.base import Base, IdMixin, TimestampMixin


class CalendarEvent(Base, IdMixin, TimestampMixin):
    """An event somebody wrote down by hand (meeting, trade show, deadline).
    Everything the AI places in the calendar from the company's data is
    computed on the fly (app.agenda.service) and is NOT stored here."""

    __tablename__ = "calendar_events"

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # meeting | trade_show | deadline | other
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
