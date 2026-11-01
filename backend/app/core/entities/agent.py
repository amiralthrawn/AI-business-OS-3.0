import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.entities.base import Base, IdMixin, TimestampMixin


class AgentProposal(Base, IdMixin, TimestampMixin):
    """Something an agent found or needs: an external finding (Veilleur), a
    question the product needs answered, or an action it already did on its
    own. Always traceable: sources are the real URLs the finding came from."""

    __tablename__ = "agent_proposals"
    __table_args__ = (UniqueConstraint("company_id", "dedupe_key", name="uq_agent_proposal_dedupe"),)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String(20), nullable=False)  # veilleur | analyste | guide
    # finding | missing_info
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="finding")
    category: Mapped[str | None] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    why: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list | None] = mapped_column(JSON)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # calendar_event | task | none
    action_type: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    action_payload: Mapped[dict | None] = mapped_column(JSON)
    # new | accepted | ignored | auto_done | undone | answered
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new", index=True)
    # What the action created, so it can be undone: {"calendar_event": id} / {"task": id}
    result_ref: Mapped[dict | None] = mapped_column(JSON)
    answer: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base, IdMixin, TimestampMixin):
    """One pass of an agent, kept so the person can see what is watched and when."""

    __tablename__ = "agent_runs"

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ok | not_configured | error
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text)
