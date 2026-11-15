"""The DM card each assignee gets: queued with the task, sent afterwards, and kept current as the task's status changes.

Same shape as the channel announcement: `record_dm` runs inside the task command (so the row and the task land together),
`send_pending` runs after the reply (so Slack can never break creating a task), and nothing here ever raises into a
request. Only people with a real Slack id get a card (the demo people's made-up ids are skipped), and only when Slack is
set up.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.config import get_settings
from database.config import SessionLocal
from models import Person, SlackDm, SlackDmMessage, Task, TaskActivity, Team
from slack import blocks, client
from slack.messages import REAL_SLACK_ID
from slack.services import home

MAX_ATTEMPTS = 5
HANDOVER_ENTRIES = 10  # how much of a task's earlier thread the new assignee's first message carries
logger = logging.getLogger(__name__)


def record_dm(db: Session, task: Task, assignee: Person | None) -> None:
    """Queue the card for `task`'s assignee. Called by the task commands before they commit."""
    if not get_settings().slack_configured or assignee is None or not REAL_SLACK_ID.match(assignee.slack_user_id or ""):
        return
    db.add(SlackDm(task_id=task.id, person_id=assignee.id))


def record_reassignment(db: Session, task: Task, new_assignee: Person, actor: Person) -> None:
    """The task is moving to `new_assignee`: the current card is marked replaced (it is closed after the reply; a card that
    was never sent is dropped), and a new card is queued for the new assignee, whose thread will start with what was
    already said on the task. Called by the task command before it commits."""
    if not get_settings().slack_configured:
        return
    live = db.scalar(select(SlackDm).where(SlackDm.task_id == task.id, SlackDm.replaced_at.is_(None)))
    if live is not None:
        live.replaced_at = datetime.now(timezone.utc)
        if live.status != "sent":
            live.status, live.last_error = "failed", "The task was reassigned before this card was sent."
        db.flush()  # the unique index allows one live card per task, so the old one is out before the new one goes in
    if REAL_SLACK_ID.match(new_assignee.slack_user_id or ""):
        db.add(SlackDm(task_id=task.id, person_id=new_assignee.id, reassigned_by=actor.id))


def thread_entries(db: Session, task: Task, *, limit: int, you: uuid.UUID, kinds: tuple[str, ...] | None = None) -> tuple[list[tuple], int]:
    """The newest `limit` timeline entries of the task, oldest first, as the lines a thread shows, and how many older ones are
    left out. Each is (who, role, kind, field, old, new, note, source, when). The role is relative to `you`, the person the
    thread is for: "you", "manager", "admin", or "previous assignee" for anyone else who acted on it."""
    query = select(TaskActivity).where(TaskActivity.task_id == task.id)
    if kinds:
        query = query.where(TaskActivity.kind.in_(kinds))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    entries = list(db.scalars(query.order_by(TaskActivity.created_at.desc()).limit(limit)))[::-1]
    people = {p.id: p for p in db.scalars(select(Person).where(Person.id.in_({e.actor_id for e in entries if e.actor_id})))}
    manager_id = team.manager_id if (team := db.get(Team, task.team_id)) else None

    def role(actor_id: uuid.UUID | None) -> str:
        if actor_id is None:
            return ""
        if actor_id == you:
            return "you"
        if actor_id == manager_id:
            return "manager"
        return "admin" if getattr(people.get(actor_id), "is_admin", False) else "previous assignee"

    lines = [
        (people[e.actor_id].name if e.actor_id in people else "Someone", role(e.actor_id), e.kind, e.field, e.old_value, e.new_value, e.note, e.source, e.created_at)
        for e in entries
    ]
    return lines, max(0, total - len(entries))


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
    if row.reassigned_by is not None:
        _post_handover(db, row, task, token)


def _post_handover(db: Session, row: SlackDm, task: Task, token: str) -> None:
    """The new assignee's first message under their card: who reassigned the task to them and what was already said and done
    on it. The card is already theirs, so a Slack problem here is logged and nothing more."""
    by = db.get(Person, row.reassigned_by)
    entries, hidden = thread_entries(db, task, limit=HANDOVER_ENTRIES, you=row.person_id, kinds=("comment", "status", "reassign"))
    text, card = blocks.handover(by.name if by else "Your manager", entries, hidden)
    try:
        ts = client.post_message(token, row.dm_channel, text, card, thread_ts=row.message_ts, color=blocks.MANAGER_BAR)
    except client.SlackError as err:
        logger.warning("Slack did not take the hand-over message for task %s: %s", task.id, err)
        return
    db.add(SlackDmMessage(dm_id=row.id, ts=ts))
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
            row = db.scalar(select(SlackDm).where(SlackDm.task_id == task_id, SlackDm.status == "sent", SlackDm.replaced_at.is_(None)))
            task = db.get(Task, task_id)
            person = db.get(Person, row.person_id) if row and row.person_id else None
            if row is None or task is None or person is None or not row.dm_channel or not row.message_ts:
                return
            text, card = blocks.card(task, person, _reviewer_note(db, task))
            client.update_message(settings.slack_bot_token, row.dm_channel, row.message_ts, text, card, color=blocks.card_color(task))
    except Exception:  # noqa: BLE001
        logger.exception("Refreshing the DM card for task %s failed", task_id)


def after_reassign(task_id: uuid.UUID, old_person_id: uuid.UUID | None) -> None:
    """After the reply to a reassignment: send the new assignee their card (and the hand-over under it), close the old card
    with a note of who has the task now, and redraw both people's Home tabs. Never raises."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            if task is None:
                return
            team_id = task.team_id
            slack_ids = [p.slack_user_id for p in (db.get(Person, old_person_id) if old_person_id else None, db.get(Person, task.assignee_id) if task.assignee_id else None) if p]
    except Exception:  # noqa: BLE001
        logger.exception("Reading task %s after its reassignment failed", task_id)
        return
    send_pending(team_id)
    close_replaced(task_id)
    for slack_id in dict.fromkeys(slack_ids):
        if REAL_SLACK_ID.match(slack_id or ""):
            home.publish(slack_id)


def close_replaced(task_id: uuid.UUID) -> None:
    """Redraw the card of the assignee the task has just left: the title, who has it now, and no buttons. Only the newest
    replaced card, so an earlier one keeps naming the person it went to. Never raises."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            row = db.scalar(
                select(SlackDm).where(SlackDm.task_id == task_id, SlackDm.replaced_at.is_not(None), SlackDm.status == "sent")
                .order_by(SlackDm.replaced_at.desc()).limit(1)
            )
            task = db.get(Task, task_id)
            if row is None or task is None or not row.dm_channel or not row.message_ts:
                return
            now_has = db.get(Person, task.assignee_id) if task.assignee_id else None
            text, card = blocks.reassigned_card(task, now_has.name if now_has else "someone else")
            client.update_message(settings.slack_bot_token, row.dm_channel, row.message_ts, text, card, color=blocks.card_color(task))
    except Exception:  # noqa: BLE001
        logger.exception("Closing the old DM card of task %s failed", task_id)


def _post_in_thread(task_id: uuid.UUID, text: str, card: list[dict], color: str) -> None:
    """Post a message in the task's DM thread (under its card) as the bot, with a side bar, and remember its ts so the whole
    thread can be removed later. Does nothing if the task has no sent card. Never raises."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            row = db.scalar(select(SlackDm).where(SlackDm.task_id == task_id, SlackDm.status == "sent", SlackDm.replaced_at.is_(None)))
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
