"""Read a team's standup channel and store the tasks it suggests.

A command: it checks who is asking, writes, and returns nothing (the caller reads the suggestions with a query).
It commits once per submission, not once per run, because every submission costs a model call and a failure half way
must not throw away the ones already paid for. A submission is recorded as read only after its suggestions are saved,
so one that failed is tried again on the next sync.

Only people on the team are read, matched to the standup app's persons by Slack id, then by email.
"""
import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import AppError
from identity.services.lookup import get_team
from models import Person, StandupRead, Task, TaskSuggestion, Team
from security.authorization import require_act
from standups.llm import extract, prompt
from standups.services import suggestions as suggestions_service
from standups.services.matching import person_matcher
from standups.standup_db import reader
from standups.states import SYNC_DAYS

STATUS_LABEL = {"todo": "To Do", "in_progress": "In Progress", "blocked": "Blocked", "review": "Review"}


def sync_team(db: Session, actor: Person, team_id: uuid.UUID, person_id: uuid.UUID | None = None) -> None:
    """Read the team's standup channel. With `person_id`, read only that person's posts, so a manager can go one person
    at a time (one model call at a time, and one failure or rate limit costs only that person)."""
    team = get_team(db, team_id)
    require_act(actor, team)
    _sync(db, team, person_id)


def sync_team_scheduled(db: Session, team_id: uuid.UUID) -> None:
    """The same read for the scheduler (`standups.scheduler`): nobody is signed in, so there is no actor to check. It only
    proposes suggestions, which wait for the manager to review; it never creates a task."""
    _sync(db, get_team(db, team_id), None)


def _sync(db: Session, team: Team, person_id: uuid.UUID | None) -> None:
    if not team.standup_channel_id:
        raise AppError("standup_channel_not_set", "This team has no standup channel yet. Ask an admin to set one.", 409)
    members = list(db.scalars(select(Person).where(Person.team_id == team.id)))
    if person_id is not None and not any(m.id == person_id for m in members):
        raise AppError("person_not_on_team", "That person is not on this team.", 404)

    today = date.today()
    suggestions_service.expire(db, team.id)
    match = person_matcher(members)

    for sub in reader.list_submissions(team.standup_channel_id, today - timedelta(days=SYNC_DAYS)):
        person = match(sub)
        if person is None or (person_id is not None and person.id != person_id):
            continue
        digest = _hash(sub)
        read = db.scalar(select(StandupRead).where(StandupRead.team_id == team.id, StandupRead.source_submission_id == sub.id))
        if read is not None and read.content_hash == digest:
            continue

        # The person's older pending suggestions go first, so the model does not skip this week's work as "already tracked".
        suggestions_service.delete_older_uncommitted(db, team.id, person.id, sub.standup_date)
        try:
            suggestions = extract.extract(sub, _tracked(db, team.id, person))
        except AppError:
            db.rollback()  # a failed model call must not cost the person their old suggestions
            raise
        have = set(db.scalars(select(TaskSuggestion.title_key).where(
            TaskSuggestion.team_id == team.id, TaskSuggestion.source_submission_id == sub.id)))
        for s in suggestions:
            key = extract.norm(s.title)
            if key in have:
                continue
            have.add(key)
            due, is_default = _due(s.due, sub.standup_date, today)
            db.add(TaskSuggestion(
                team_id=team.id, person_id=person.id, source_submission_id=sub.id, standup_date=sub.standup_date,
                late_reply=sub.is_late_reply, title=s.title, title_key=key, description=s.description, kind=s.kind,
                priority=s.priority, start_at=sub.standup_date, due_at=due, due_is_default=is_default,
                subtasks=s.subtasks, evidence_quote=s.evidence_quote, related_to=s.related_to,
                model=get_settings().llm_model, prompt_hash=prompt.PROMPT_HASH,
            ))
        if read is None:
            db.add(StandupRead(team_id=team.id, source_submission_id=sub.id, content_hash=digest))
        else:
            read.content_hash, read.read_at = digest, datetime.now(timezone.utc)
        db.commit()


def _hash(sub: reader.Submission) -> str:
    """A hash of everything the model reads. The standup app overwrites a resubmitted row without touching its
    created_at, so this is the only way an edit shows."""
    text = "\x1f".join(str(part or "") for part in (sub.last_week, sub.this_week, sub.blockers, sub.combined, sub.raw_content))
    return hashlib.sha256(text.encode()).hexdigest()


def _tracked(db: Session, team_id: uuid.UUID, person: Person) -> list[extract.Tracked]:
    """The team's open tasks and the suggestions still waiting, so the model does not propose them again."""
    names = {p.id: p.name for p in db.scalars(select(Person).where(Person.team_id == team_id))}
    tracked = [
        extract.Tracked(t.title, STATUS_LABEL[t.status], names.get(t.assignee_id, "nobody"), t.assignee_id == person.id)
        for t in db.scalars(select(Task).where(Task.team_id == team_id, Task.status != "done").order_by(Task.created_at))
    ]
    tracked += [
        extract.Tracked(s.title, "suggestion waiting", names.get(s.person_id, "nobody"), s.person_id == person.id)
        for s in db.scalars(select(TaskSuggestion).where(TaskSuggestion.team_id == team_id, TaskSuggestion.state == "pending"))
    ]
    return tracked


def _due(stated: date | None, standup_date: date, today: date) -> tuple[date | None, bool]:
    """Decide a suggestion's due date by the same rule a task has: never in the past.

    | the standup states a date | that date is today or later | result                                  |
    | yes                       | yes                         | that date (the manager's, not a default)|
    | yes                       | no, it has passed           | no date (the manager can set one)       |
    | no                        | Friday of its week is today or later | that Friday, shown as a default |
    | no                        | that Friday has passed      | no date                                 |
    """
    if stated is not None:
        return (stated, False) if stated >= today else (None, False)
    friday = standup_date - timedelta(days=standup_date.weekday()) + timedelta(days=4)
    return (friday, True) if friday >= today else (None, False)
