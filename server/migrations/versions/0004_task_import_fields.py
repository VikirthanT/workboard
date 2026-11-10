"""tasks: support, project, stage and start date (bulk import fields)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("support_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tasks", sa.Column("project", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("stage", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("start_at", sa.Date(), nullable=True))


def downgrade() -> None:
    for column in ("start_at", "stage", "project", "support_id"):
        op.drop_column("tasks", column)
