import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.config import Base

SUGGESTION_STATES = ("pending", "approved", "rejected")
SUGGESTION_KINDS = ("blocker", "deadline", "handover", "carry_over", "new")
SUGGESTION_PRIORITIES = ("low", "medium", "high")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


class TaskSuggestion(Base):
    """A task proposed from one person's standup. Only approving it creates a task (`task_id`); until then it is not on
    any board. `source_submission_id` is the standup app's id for the submission (not a foreign key: that database is
    theirs), and `evidence_quote` is the exact line of that submission that supports it."""

    __tablename__ = "task_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    # The person who posted the standup, matched to our directory; the suggestion is for them.
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    source_submission_id: Mapped[int] = mapped_column(Integer)
    standup_date: Mapped[date] = mapped_column(Date)
    late_reply: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    title: Mapped[str] = mapped_column(String)
    # The normalised title, so the same suggestion read twice is stored once.
    title_key: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)
    start_at: Mapped[date | None] = mapped_column(Date)
    due_at: Mapped[date | None] = mapped_column(Date)
    # True when the standup stated no date and due_at is the Friday default; editing the date makes it the manager's own.
    due_is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    subtasks: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    evidence_quote: Mapped[str] = mapped_column(String)
    related_to: Mapped[str | None] = mapped_column(String)

    state: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    # When it last became pending, approved or rejected: the 3-day clean-up of pending and rejected ones counts from here.
    state_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))

    model: Mapped[str] = mapped_column(String)
    prompt_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(_in("state", SUGGESTION_STATES), name="ck_task_suggestions_state"),
        CheckConstraint(_in("kind", SUGGESTION_KINDS), name="ck_task_suggestions_kind"),
        CheckConstraint(_in("priority", SUGGESTION_PRIORITIES), name="ck_task_suggestions_priority"),
        UniqueConstraint("team_id", "source_submission_id", "title_key", name="uq_task_suggestions_once_per_submission"),
        Index("ix_task_suggestions_team_person", "team_id", "person_id"),
    )


class StandupRead(Base):
    """A submission we have already read for a team, with a hash of its text. A resubmission overwrites the standup
    app's row without changing its created_at, so a changed hash is how an edit is noticed; an unchanged one is skipped,
    including one that produced no suggestions."""

    __tablename__ = "standup_reads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    source_submission_id: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("team_id", "source_submission_id", name="uq_standup_reads_team_submission"),)
