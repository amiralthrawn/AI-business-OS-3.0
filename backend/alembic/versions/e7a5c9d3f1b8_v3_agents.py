"""V3: agent_proposals, agent_runs, calendar_events.source

Revision ID: e7a5c9d3f1b8
Revises: d6f4b8c2e5a7
"""

import sqlalchemy as sa
from alembic import op

revision = "e7a5c9d3f1b8"
down_revision = "d6f4b8c2e5a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.add_column(sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"))
    op.create_table(
        "agent_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("why", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result_ref", sa.JSON(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "dedupe_key", name="uq_agent_proposal_dedupe"),
    )
    op.create_index("ix_agent_proposals_company_id", "agent_proposals", ["company_id"])
    op.create_index("ix_agent_proposals_status", "agent_proposals", ["status"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent", sa.String(length=20), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("found", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
    )
    op.create_index("ix_agent_runs_company_id", "agent_runs", ["company_id"])
    op.create_index("ix_agent_runs_agent", "agent_runs", ["agent"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("agent_proposals")
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_column("source")
