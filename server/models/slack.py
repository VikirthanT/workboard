import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from database.config import Base

OUTBOX_STATES = ("pending", "sent", "failed")


class SlackDmMessage(Base):
    """A message the bot posted in a task's DM thread (a comment shown there). The ts of each is kept so the whole thread
    can be deleted later: a bot can delete only its own messages, so every message in the thread is the bot's."""

    __tablename__ = "slack_dm_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    dm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slack_dms.id", ondelete="CASCADE"))
    ts: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_slack_dm_messages_dm", "dm_id"),)


class SlackDm(Base):
    """The DM card a task's assignee got in Slack. One per task: created pending with the task (like the channel
    announcement), sent afterwards, then its `dm_channel` and `message_ts` say which message to update when the task's
    status changes on either side. Only queued for assignees with a real Slack id, and only when Slack is set up."""

    __tablename__ = "slack_dms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), unique=True)
    # Who the card was sent to (the assignee when it was created); a reassignment later does not move the old card.
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String)
    dm_channel: Mapped[str | None] = mapped_column(String)
    message_ts: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status in ('pending', 'sent', 'failed')", name="ck_slack_dms_status"),
        Index("ix_slack_dms_status", "status"),
    )


class SlackOutbox(Base):
    """One new task waiting to be announced in its team's Slack channel. The task commands add the row in the same
    transaction that creates the task, so a task is never created without its announcement being queued, and a Slack
    outage never blocks creating a task. A separate step sends whatever is pending for a team as one message and one
    PDF. Rows are only queued when Slack is set up."""

    __tablename__ = "slack_outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    # A task deleted before it was announced takes its row with it (there is nothing left to announce).
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status in ('pending', 'sent', 'failed')", name="ck_slack_outbox_status"),
        Index("ix_slack_outbox_team_status", "team_id", "status"),
    )
