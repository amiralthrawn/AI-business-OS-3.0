import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.entities.base import Base, IdMixin, LinkableMixin, TimestampMixin


class Contact(Base, IdMixin, TimestampMixin, LinkableMixin):
    """A person, linked via LinkableMixin to the Supplier or Customer they
    belong to -- or left unresolved (both LinkableMixin fields `None`) when
    that identity can't be reliably determined yet, e.g. a brand-new sender
    or website visitor the External Connectivity Layer (app.connectors)
    can't yet match to an existing Supplier/Customer (see brain/connectors.md).
    `company_id` was added in step 21 when Contact went from an unused
    structural placeholder to an entity connector ingestion actually writes."""

    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str | None] = mapped_column(String(120))
