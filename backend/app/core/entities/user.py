import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.entities.base import Base, IdMixin, TimestampMixin


class Role(str, enum.Enum):
    """The job a user holds (V2). Drives navigation, what can be edited and
    which actions can be triggered -- see app.access.policy for the matrix.

    V3: these are the *base* roles. A director builds the company's own roles
    on top of them (CustomRole) without touching this list."""

    DIRECTOR = "director"
    SALES = "sales"
    PROCUREMENT = "procurement"
    OPERATIONS = "operations"
    HR = "hr"
    EMPLOYEE = "employee"
    # V3: finance follow-up (receivables, payables, cash) for an in-house or
    # external accountant.
    ACCOUNTANT = "accountant"


class CustomRole(Base, IdMixin, TimestampMixin):
    """A role a director created for their own company (V3): a name
    ("Responsable logistique"), a base role it starts from, and the
    permissions added to / removed from that base. Profiles holding it get
    base defaults + these changes + their own per-profile changes
    (app.access.policy.effective_permissions)."""

    __tablename__ = "custom_roles"

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    access_grants: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    access_revokes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class UserProfile(Base, IdMixin, TimestampMixin):
    """A person using the OS, their role and (V3) their account.

    A profile becomes a sign-in account once it has a password: either the
    director who created the company at sign-up, or someone who accepted an
    invitation (`invite_token_hash`, a SHA-256 of the one-time link token --
    the token itself is never stored)."""

    __tablename__ = "users"

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Unique across all companies: it is the sign-in identifier. Stored lower-case.
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # V2.1 custom access: permissions a director added to / removed from the
    # role's defaults for this profile (app.access.policy.effective_permissions).
    access_grants: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    access_revokes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # V3 -- the person's position in the company and the company-defined role
    # they hold (when set, `role` mirrors the custom role's base role).
    job_title: Mapped[str | None] = mapped_column(String(120))
    custom_role_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("custom_roles.id"), nullable=True, index=True)
    custom_role: Mapped["CustomRole | None"] = relationship()

    # V3 -- authentication.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def account_status(self) -> str:
        """"active" (can sign in), "invited" (link sent, not accepted yet) or
        "no_access" (a profile without an account, e.g. demo data)."""

        if self.password_hash:
            return "active"
        if self.invite_token_hash:
            return "invited"
        return "no_access"
