"""tasks and task_activity

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UUID_DEFAULT = sa.text("gen_random_uuid()")
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("creator_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("returned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('todo', 'in_progress', 'blocked', 'review', 'done')", name="ck_tasks_status"),
        sa.CheckConstraint("priority in ('low', 'medium', 'high')", name="ck_tasks_priority"),
    )
    op.create_index("ix_tasks_team_id", "tasks", ["team_id"])
    op.create_table(
        "task_activity",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="workboard"),
        sa.Column("field", sa.String(), nullable=True),
        sa.Column("old_value", sa.String(), nullable=True),
        sa.Column("new_value", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("kind in ('created', 'status', 'edit', 'reassign', 'comment')", name="ck_task_activity_kind"),
        sa.CheckConstraint("source in ('workboard', 'slack')", name="ck_task_activity_source"),
    )
    op.create_index("ix_task_activity_task_id_created_at", "task_activity", ["task_id", "created_at"])
    # Append-only for edits. UPDATE is refused; DELETE stays allowed because deleting a task or team cascades here.
    # A person's removal would SET NULL on actor_id, which is an UPDATE, so actor_id is exempt from the refusal.
    op.execute(
        """
        CREATE FUNCTION task_activity_refuse_update() RETURNS trigger AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'actor_id') IS DISTINCT FROM (to_jsonb(OLD) - 'actor_id') THEN
                RAISE EXCEPTION 'task_activity is append-only (UPDATE refused)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER task_activity_append_only
        BEFORE UPDATE ON task_activity
        FOR EACH ROW EXECUTE FUNCTION task_activity_refuse_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER task_activity_append_only ON task_activity")
    op.execute("DROP FUNCTION task_activity_refuse_update()")
    op.drop_table("task_activity")
    op.drop_table("tasks")
