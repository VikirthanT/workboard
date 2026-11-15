"""slack_dms: a task can have several DM cards over its life, one live at a time, so a reassigned task gets a card for its new assignee

Until now a task had exactly one card (task_id unique) and a reassignment left it with the first assignee. Now the old card
is marked replaced (`replaced_at`) and a new live one is queued for the new assignee (`reassigned_by` says who moved it).
At most one card per task is live: the unique index covers only the rows not yet replaced.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("slack_dms_task_id_key", "slack_dms", type_="unique")
    op.add_column("slack_dms", sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("slack_dms", sa.Column("reassigned_by", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True))
    op.create_index("uq_slack_dms_live_task", "slack_dms", ["task_id"], unique=True, postgresql_where=sa.text("replaced_at IS NULL"))


def downgrade() -> None:
    # Only the live card of each task can stay: the replaced ones are the history this table no longer keeps.
    op.drop_index("uq_slack_dms_live_task", table_name="slack_dms")
    op.execute("DELETE FROM slack_dms WHERE replaced_at IS NOT NULL")
    op.drop_column("slack_dms", "reassigned_by")
    op.drop_column("slack_dms", "replaced_at")
    op.create_unique_constraint("slack_dms_task_id_key", "slack_dms", ["task_id"])
