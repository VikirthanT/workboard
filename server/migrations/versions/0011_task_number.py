"""tasks.number: a short id people can read out (shown as #12), one counter for every task, the same in the Workboard and in Slack

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE tasks_number_seq")
    op.add_column("tasks", sa.Column("number", sa.Integer(), nullable=True))
    # Existing tasks are numbered in the order they were created, so the oldest is #1.
    op.execute(
        "UPDATE tasks SET number = numbered.n FROM "
        "(SELECT id, row_number() OVER (ORDER BY created_at, id) AS n FROM tasks) AS numbered WHERE tasks.id = numbered.id"
    )
    op.execute("SELECT setval('tasks_number_seq', coalesce((SELECT max(number) FROM tasks), 0) + 1, false)")
    op.execute("ALTER TABLE tasks ALTER COLUMN number SET DEFAULT nextval('tasks_number_seq')")
    op.execute("ALTER TABLE tasks ALTER COLUMN number SET NOT NULL")
    op.create_unique_constraint("uq_tasks_number", "tasks", ["number"])
    op.execute("ALTER SEQUENCE tasks_number_seq OWNED BY tasks.number")


def downgrade() -> None:
    op.drop_constraint("uq_tasks_number", "tasks", type_="unique")
    op.drop_column("tasks", "number")  # the sequence is owned by the column, so it goes with it
