"""V3 configuration phase: business_contexts.configuration

Revision ID: b4d2f6a8c1e3
Revises: a3c9e1f0b7d2
"""

import sqlalchemy as sa
from alembic import op

revision = "b4d2f6a8c1e3"
down_revision = "a3c9e1f0b7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("business_contexts") as batch:
        batch.add_column(sa.Column("configuration", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("business_contexts") as batch:
        batch.drop_column("configuration")
