"""slack_dms: the DM card each task's assignee got in Slack

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slack_dms",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("dm_channel", sa.String(), nullable=True),
        sa.Column("message_ts", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'sent', 'failed')", name="ck_slack_dms_status"),
    )
    op.create_index("ix_slack_dms_status", "slack_dms", ["status"])


def downgrade() -> None:
    op.drop_index("ix_slack_dms_status", table_name="slack_dms")
    op.drop_table("slack_dms")
