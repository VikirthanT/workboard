import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from database.config import Base

STATUSES = ("todo", "in_progress", "blocked", "review", "done")
PRIORITIES = ("low", "medium", "high")
ACTIVITY_KINDS = ("created", "status", "edit", "reassign", "comment")
SOURCES = ("workboard", "slack")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    # Deleting a team erases its tasks (and, through them, their activity).
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="", server_default="")
    status: Mapped[str] = mapped_column(String, default="todo", server_default="todo")
    priority: Mapped[str] = mapped_column(String, default="medium", server_default="medium")
    due_at: Mapped[date | None] = mapped_column(Date)
    # People are never deleted (only marked inactive), so SET NULL is a safety net, not a normal path.
    creator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
    returned_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # Phase 2 (Slack Accept)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(_in("status", STATUSES), name="ck_tasks_status"),
        CheckConstraint(_in("priority", PRIORITIES), name="ck_tasks_priority"),
        Index("ix_tasks_team_id", "team_id"),
    )


class TaskActivity(Base):
    """Timeline and comments in one append-only table (a comment is an entry of kind 'comment').
    A trigger (migration 0002) refuses UPDATE; DELETE is allowed only so a deleted task or team can take its
    history with it."""

    __tablename__ = "task_activity"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="workboard", server_default="workboard")
    field: Mapped[str | None] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(String)
    new_value: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(_in("kind", ACTIVITY_KINDS), name="ck_task_activity_kind"),
        CheckConstraint(_in("source", SOURCES), name="ck_task_activity_source"),
        Index("ix_task_activity_task_id_created_at", "task_id", "created_at"),
    )
