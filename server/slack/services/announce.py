"""Send what is waiting for a team as one message and one PDF in the team's standup channel.

`flush_team` is run after a request has been answered (FastAPI's background tasks), with its own database session. It
never raises: whoever created the tasks must not see a Slack problem. A failure is written on the queued rows, which stay
pending and are sent with the next batch, until MAX_ATTEMPTS, then they are marked failed.
"""
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from database.config import SessionLocal
from models import Person, SlackOutbox, Task, TaskSuggestion, Team
from slack import client, messages
from slack.pdf import AnnouncedTask, build_pdf
from slack.services import dm

MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)


def flush_team(team_id: uuid.UUID, heading: str = messages.HEADING_BULK) -> None:
    """Everything Slack has waiting for this team: the channel announcement, then the assignees' DM cards. Each is
    independent: one failing does not stop the other."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    try:
        with SessionLocal() as db:
            _send_pending(db, team_id, settings.slack_bot_token, heading)
    except Exception:  # noqa: BLE001 - a Slack or PDF problem must never reach the person who created the tasks
        logger.exception("The Slack announcement for team %s failed", team_id)
    dm.send_pending(team_id)


def _send_pending(db: Session, team_id: uuid.UUID, token: str, heading: str) -> None:
    # shortcut: the heading comes from the flush that runs, so a row retried after a Slack failure may carry the other
    # source's wording; upgrade by storing the source on the outbox row.
    # skip_locked: a second flush at the same moment finds nothing, so the same tasks are never announced twice.
    rows = list(db.scalars(
        select(SlackOutbox).where(SlackOutbox.team_id == team_id, SlackOutbox.status == "pending")
        .order_by(SlackOutbox.created_at).with_for_update(skip_locked=True)
    ))
    if not rows:
        return
    team = db.get(Team, team_id)
    if team is None or not team.standup_channel_id:
        _fail(db, rows, "The team has no standup channel to post in.", final=True)
        return

    tasks = list(db.scalars(select(Task).where(Task.id.in_([r.task_id for r in rows])).order_by(Task.created_at, Task.title)))
    tasks = [t for t in tasks if t.assignee_id != team.manager_id]  # the manager's own tasks are not announced to the team
    if not tasks:  # nothing for the channel (the manager's DM card is sent separately)
        now = datetime.now(timezone.utc)
        for row in rows:
            row.status, row.sent_at, row.last_error = "sent", now, None
        db.commit()
        return
    person_ids = {t.assignee_id for t in tasks} | {t.creator_id for t in tasks}
    people = {p.id: p for p in db.scalars(select(Person).where(Person.id.in_(person_ids)))}
    # A task made from a standup suggestion carries the standup line it came from; the PDF shows it under the description.
    quotes = dict(db.execute(
        select(TaskSuggestion.task_id, TaskSuggestion.evidence_quote).where(TaskSuggestion.task_id.in_([t.id for t in tasks]))
    ).all())
    announced = [
        AnnouncedTask(
            title=t.title, description=t.description, priority=t.priority, due_at=t.due_at, start_at=t.start_at,
            assignee_name=people[t.assignee_id].name if t.assignee_id in people else "Unassigned",
            assignee_slack_id=people[t.assignee_id].slack_user_id if t.assignee_id in people else None,
            assignee_email=people[t.assignee_id].email if t.assignee_id in people else None,
            quote=quotes.get(t.id), project=t.project, stage=t.stage,
        )
        for t in tasks
    ]
    creator = people.get(tasks[0].creator_id) if tasks else None
    added_by = creator.name if creator else "a manager"
    today = date.today()
    text = messages.announcement(announced, heading)
    pdf = build_pdf(team.name, added_by, announced, today)

    try:
        client.post_with_pdf(token, team.standup_channel_id, text, f"Task-{today.strftime('%d-%b-%Y')}.pdf", pdf)
    except client.SlackError as err:
        logger.warning("Slack did not take the announcement for team %s: %s", team_id, err)
        _fail(db, rows, str(err))
        return
    now = datetime.now(timezone.utc)
    for row in rows:
        row.status, row.sent_at, row.last_error = "sent", now, None
    db.commit()


def _fail(db: Session, rows: list[SlackOutbox], reason: str, *, final: bool = False) -> None:
    for row in rows:
        row.attempts += 1
        row.last_error = reason[:300]
        if final or row.attempts >= MAX_ATTEMPTS:
            row.status = "failed"
    db.commit()
