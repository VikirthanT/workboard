"""task_suggestions and standup_reads: tasks proposed from standups, and which submissions were already read

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_suggestions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_submission_id", sa.Integer(), nullable=False),
        sa.Column("standup_date", sa.Date(), nullable=False),
        sa.Column("late_reply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("title_key", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("start_at", sa.Date(), nullable=True),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("due_is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("subtasks", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence_quote", sa.String(), nullable=False),
        sa.Column("related_to", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("state_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("state in ('pending', 'approved', 'rejected')", name="ck_task_suggestions_state"),
        sa.CheckConstraint("kind in ('blocker', 'deadline', 'handover', 'carry_over', 'new')", name="ck_task_suggestions_kind"),
        sa.CheckConstraint("priority in ('low', 'medium', 'high')", name="ck_task_suggestions_priority"),
        sa.UniqueConstraint("team_id", "source_submission_id", "title_key", name="uq_task_suggestions_once_per_submission"),
    )
    op.create_index("ix_task_suggestions_team_person", "task_suggestions", ["team_id", "person_id"])

    op.create_table(
        "standup_reads",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_submission_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("team_id", "source_submission_id", name="uq_standup_reads_team_submission"),
    )


def downgrade() -> None:
    op.drop_table("standup_reads")
    op.drop_index("ix_task_suggestions_team_person", table_name="task_suggestions")
    op.drop_table("task_suggestions")
