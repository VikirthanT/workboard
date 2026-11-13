"""slack_dm_messages: the messages the bot posted in a task's DM thread, so the thread can be removed later

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slack_dm_messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("dm_id", sa.Uuid(), sa.ForeignKey("slack_dms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_slack_dm_messages_dm", "slack_dm_messages", ["dm_id"])


def downgrade() -> None:
    op.drop_index("ix_slack_dm_messages_dm", table_name="slack_dm_messages")
    op.drop_table("slack_dm_messages")
