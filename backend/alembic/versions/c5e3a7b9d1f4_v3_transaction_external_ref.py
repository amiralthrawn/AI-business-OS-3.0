"""V3: transactions.external_ref (idempotent imports)

Revision ID: c5e3a7b9d1f4
Revises: b4d2f6a8c1e3
"""

import sqlalchemy as sa
from alembic import op

revision = "c5e3a7b9d1f4"
down_revision = "b4d2f6a8c1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("external_ref", sa.String(length=120), nullable=True))
        batch.create_index("ix_transactions_external_ref", ["external_ref"])


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_index("ix_transactions_external_ref")
        batch.drop_column("external_ref")
