import uuid

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.entities.base import Base, IdMixin, LinkableMixin, TimestampMixin


class Document(Base, IdMixin, TimestampMixin, LinkableMixin):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_source_external_id", "source", "external_id", unique=True),)

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(String(500))
    # Same provenance convention as Communication.source/external_id (step
    # 21) -- e.g. an email attachment ingested alongside its Communication.
    source: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
