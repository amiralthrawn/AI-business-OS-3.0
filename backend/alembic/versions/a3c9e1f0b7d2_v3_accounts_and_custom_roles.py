"""v3 accounts, invitations and company-defined roles

V3 turns profiles into sign-in accounts (password hash, last login,
single-use invitation link stored as a SHA-256), makes the email the unique
sign-in identifier, adds the accountant base role, and lets a director define
the company's own roles (`custom_roles`) and each person's position
(`job_title`). See app/auth and brain/permissions.md.

The Event Log gains `company_id` (app.core.events.tenant), so one company's
timeline and decisions never show in another's. Events already logged are
assigned to the company when the database holds exactly one; otherwise they
stay unassigned and are hidden from every signed-in company.

Existing emails are normalized to lower case before the unique constraint is
added; two profiles sharing an email would make this migration fail and must
be fixed by hand first.

Revision ID: a3c9e1f0b7d2
Revises: f3b8d5a2c7e1
Create Date: 2026-10-30 22:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3c9e1f0b7d2"
down_revision: Union[str, None] = "f3b8d5a2c7e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = ("DIRECTOR", "SALES", "PROCUREMENT", "OPERATIONS", "HR", "EMPLOYEE", "ACCOUNTANT")


def _role_type(bind) -> sa.types.TypeEngine:
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*ROLES, name="role", create_type=False)
    return sa.Enum(*ROLES, name="role")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'ACCOUNTANT'")

    op.create_table(
        "custom_roles",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_role", _role_type(bind), nullable=False),
        sa.Column("access_grants", sa.JSON(), nullable=False),
        sa.Column("access_revokes", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_custom_roles_company_id"), "custom_roles", ["company_id"], unique=False)

    op.execute("UPDATE users SET email = lower(trim(email)) WHERE email IS NOT NULL")
    op.execute("UPDATE users SET email = NULL WHERE email = ''")

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("job_title", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("custom_role_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("invite_token_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_users_custom_role_id", "custom_roles", ["custom_role_id"], ["id"])
        batch.create_index("ix_users_custom_role_id", ["custom_role_id"], unique=False)
        batch.create_index("ix_users_invite_token_hash", ["invite_token_hash"], unique=False)
        batch.create_unique_constraint("uq_users_email", ["email"])

    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("company_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_events_company_id", "companies", ["company_id"], ["id"])
        batch.create_index("ix_events_company_id", ["company_id"], unique=False)
    op.execute(
        "UPDATE events SET company_id = (SELECT id FROM companies) "
        "WHERE company_id IS NULL AND (SELECT count(*) FROM companies) = 1"
    )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.drop_index("ix_events_company_id")
        batch.drop_constraint("fk_events_company_id", type_="foreignkey")
        batch.drop_column("company_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_email", type_="unique")
        batch.drop_index("ix_users_invite_token_hash")
        batch.drop_index("ix_users_custom_role_id")
        batch.drop_constraint("fk_users_custom_role_id", type_="foreignkey")
        batch.drop_column("invite_expires_at")
        batch.drop_column("invite_token_hash")
        batch.drop_column("last_login_at")
        batch.drop_column("password_hash")
        batch.drop_column("custom_role_id")
        batch.drop_column("job_title")
    op.drop_index(op.f("ix_custom_roles_company_id"), table_name="custom_roles")
    op.drop_table("custom_roles")
    # PostgreSQL cannot drop a value from an enum type: ACCOUNTANT stays in
    # `role`, unused.
