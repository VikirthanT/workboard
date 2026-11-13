"""The DM card each assignee gets: queued with the task, sent afterwards, and kept current as the task's status changes.

Same shape as the channel announcement: `record_dm` runs inside the task command (so the row and the task land together),
`send_pending` runs after the reply (so Slack can never break creating a task), and nothing here ever raises into a
request. Only people with a real Slack id get a card (the demo people's made-up ids are skipped), and only when Slack is
set up.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from database.config import SessionLocal
from models import Person, SlackDm, SlackDmMessage, Task, TaskActivity, Team
from slack import blocks, client
from slack.messages import REAL_SLACK_ID

MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)


def record_dm(db: Session, task: Task, assignee: Person | None) -> None:
    """Queue the card for `task`'s assignee. Called by the task commands before they commit."""
    if not get_settings().slack_configured or assignee is None or not REAL_SLACK_ID.match(assignee.slack_user_id or ""):
        return
    db.add(SlackDm(task_id=task.id, person_id=assignee.id))


def send_pending(team_id: uuid.UUID) -> None:
    """Send every queued card of this team's tasks. Never raises."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            rows = list(db.scalars(
                select(SlackDm).join(Task, Task.id == SlackDm.task_id)
                .where(Task.team_id == team_id, SlackDm.status == "pending").order_by(SlackDm.created_at)
                .with_for_update(of=SlackDm, skip_locked=True)
            ))
            for row in rows:
                _send(db, row, settings.slack_bot_token)
    except Exception:  # noqa: BLE001 - a Slack problem must never reach the person who created the task
        logger.exception("Sending the DM cards for team %s failed", team_id)


def _send(db: Session, row: SlackDm, token: str) -> None:
    task = db.get(Task, row.task_id)
    person = db.get(Person, row.person_id) if row.person_id else None
    if task is None or person is None or not person.slack_user_id:
        row.status, row.last_error = "failed", "The task or its assignee is gone."
        db.commit()
        return
    text, card = blocks.card(task, person, _reviewer_note(db, task))
    try:
        channel = client.open_dm(token, person.slack_user_id)
        ts = client.post_message(token, channel, text, card, color=blocks.card_color(task))
    except client.SlackError as err:
        logger.warning("Slack did not take the DM for task %s: %s", task.id, err)
        row.attempts += 1
        row.last_error = str(err)[:300]
        if row.attempts >= MAX_ATTEMPTS:
            row.status = "failed"
        db.commit()
        return
    row.dm_channel, row.message_ts, row.status, row.last_error = channel, ts, "sent", None
    row.sent_at = datetime.now(timezone.utc)
    db.commit()


def _reviewer_note(db: Session, task: Task) -> tuple[str, str] | None:
    """Once a task is Done: who marked it done and the remarks they gave (the board requires remarks for every Done), the
    last message from the reviewer, shown on the locked card."""
    if task.status != "done":
        return None
    entry = db.scalar(
        select(TaskActivity)
        .where(TaskActivity.task_id == task.id, TaskActivity.kind == "status", TaskActivity.new_value == "done")
        .order_by(TaskActivity.created_at.desc()).limit(1)
    )
    if entry is None or not entry.note:
        return None
    author = db.get(Person, entry.actor_id) if entry.actor_id else None
    return (author.name if author else "Your manager", entry.note)


def refresh_card(task_id: uuid.UUID) -> None:
    """Redraw the task's DM card from its current state (buttons and status), after a change on either side. Never raises."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            row = db.scalar(select(SlackDm).where(SlackDm.task_id == task_id, SlackDm.status == "sent"))
            task = db.get(Task, task_id)
            person = db.get(Person, row.person_id) if row and row.person_id else None
            if row is None or task is None or person is None or not row.dm_channel or not row.message_ts:
                return
            text, card = blocks.card(task, person, _reviewer_note(db, task))
            client.update_message(settings.slack_bot_token, row.dm_channel, row.message_ts, text, card, color=blocks.card_color(task))
    except Exception:  # noqa: BLE001
        logger.exception("Refreshing the DM card for task %s failed", task_id)


def _post_in_thread(task_id: uuid.UUID, text: str, card: list[dict], color: str) -> None:
    """Post a message in the task's DM thread (under its card) as the bot, with a side bar, and remember its ts so the whole
    thread can be removed later. Does nothing if the task has no sent card. Never raises."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            row = db.scalar(select(SlackDm).where(SlackDm.task_id == task_id, SlackDm.status == "sent"))
            if row is None or not row.dm_channel or not row.message_ts:
                return
            ts = client.post_message(settings.slack_bot_token, row.dm_channel, text, card, thread_ts=row.message_ts, color=color)
            db.add(SlackDmMessage(dm_id=row.id, ts=ts))
            db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Posting in the DM thread of task %s failed", task_id)


def post_comment(task_id: uuid.UUID, author: str, role: str, text: str) -> None:
    """A comment in the task's DM thread, with the bar for its side (teal for the manager, grey for the assignee's own)."""
    _post_in_thread(task_id, *blocks.comment_line(author, role, text), color=blocks.comment_color(role))


def post_move(task_id: uuid.UUID, actor_id: uuid.UUID, to: str, note: str | None) -> None:
    """Every status move, by anyone, in the task's DM thread: who moved it and where, with the remarks or reason when there
    is one (Done, Blocked, a move back, a send-back or a reopen). Never raises."""
    reason = (note or "").strip()
    try:
        with SessionLocal() as db:
            task, actor = db.get(Task, task_id), db.get(Person, actor_id)
            team = db.get(Team, task.team_id) if task else None
            if task is None or actor is None:
                return
            role = "you" if task.assignee_id == actor.id else ("manager" if team is not None and team.manager_id == actor.id else "admin")
            name = actor.name
    except Exception:  # noqa: BLE001
        logger.exception("Reading the move of task %s for the DM thread failed", task_id)
        return
    _post_in_thread(task_id, *blocks.move_line(name, role, to, reason), color=blocks.comment_color(role))


def post_manager_comment(task_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    """Show a comment made on the board in the assignee's DM thread, with the manager's bar. Comments that came from Slack are
    already there, so only board comments are posted."""
    try:
        with SessionLocal() as db:
            entry = db.get(TaskActivity, entry_id)
            author = db.get(Person, entry.actor_id) if entry and entry.actor_id else None
            task = db.get(Task, task_id)
            if entry is None or entry.kind != "comment" or entry.source != "workboard" or author is None or task is None or not entry.note:
                return
            team = db.get(Team, task.team_id)
            role = "manager" if team is not None and team.manager_id == author.id else "admin"
            name, said = author.name, entry.note
    except Exception:  # noqa: BLE001
        logger.exception("Reading comment %s for the DM thread failed", entry_id)
        return
    post_comment(task_id, name, role, said)
