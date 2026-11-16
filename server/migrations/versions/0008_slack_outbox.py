"""slack_outbox: new tasks waiting to be announced in their team's Slack channel

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slack_outbox",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'sent', 'failed')", name="ck_slack_outbox_status"),
    )
    op.create_index("ix_slack_outbox_team_status", "slack_outbox", ["team_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_slack_outbox_team_status", table_name="slack_outbox")
    op.drop_table("slack_outbox")
