"""Task commands: create, edit, delete, move, comment.

Each one checks, writes, commits once and returns nothing; a command that creates something takes its new id from
the caller. Who may do what lives in security.authorization. Mirrors client/src/mocks/handlers.ts.
"""
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity import states as identity_states
from identity.services import audit
from identity.services.lookup import get_person, get_team
from models import Person, Task, Team
from security import authorization
from tasks import states
from tasks.services import activity
from tasks.services.deletion_audit import record_task_deleted
from tasks.services.import_parse import ImportRow, RowError
from tasks.services.lookup import get_task_and_team, own_team


def create_task(
    db: Session,
    actor: Person,
    task_id: uuid.UUID,
    title: str,
    description: str,
    priority: str,
    due_at: date | None,
    assignee_id: uuid.UUID,
    today: date | None = None,
    support_id: uuid.UUID | None = None,
    project: str | None = None,
    stage: str | None = None,
    start_at: date | None = None,
) -> None:
    """The task lands on the actor's own team; anyone else is refused (an admin who runs a team uses that team)."""
    team = own_team(db, actor)
    _add_task(
        db, actor, team, task_id, title, description, priority, due_at, assignee_id, today,
        support_id, project, stage, start_at,
    )
    db.commit()


def import_tasks(db: Session, actor: Person, rows: list[ImportRow], today: date | None = None, dry_run: bool = False) -> None:
    """Create every row on the actor's own team in one transaction: if any row breaks a task rule, none is saved
    and `ImportRejected` lists each row's problem. `dry_run` runs every check and then saves nothing (the preview)."""
    team = own_team(db, actor)
    errors: list[RowError] = []
    for row in rows:
        try:
            _add_task(
                db, actor, team, uuid.uuid4(), row.title, row.description, row.priority, row.due_at,
                row.assignee_id, today, row.support_id, row.project, row.stage, row.start_at,
            )
        except AppError as err:
            errors.append(RowError(row.number, "", err.message))
    if errors:
        db.rollback()
        raise ImportRejected(errors)
    if dry_run:
        db.rollback()
    else:
        db.commit()


class ImportRejected(Exception):
    def __init__(self, errors: list[RowError]):
        super().__init__("Some rows broke a task rule.")
        self.errors = errors


def _add_task(
    db: Session,
    actor: Person,
    team: Team,
    task_id: uuid.UUID,
    title: str,
    description: str,
    priority: str,
    due_at: date | None,
    assignee_id: uuid.UUID,
    today: date | None,
    support_id: uuid.UUID | None,
    project: str | None,
    stage: str | None,
    start_at: date | None,
) -> None:
    """Check and add one task and its first timeline entry; the caller commits."""
    _require_not_past(due_at, today)
    _require_start_not_after_due(start_at, due_at)
    task = Task(
        id=task_id,
        team_id=team.id,
        title=_clean_title(title),
        description=description.strip(),
        priority=priority,
        due_at=due_at,
        creator_id=actor.id,
        assignee_id=_assignee_on(db, team, assignee_id).id,
        support_id=_support(db, support_id).id if support_id else None,
        project=_label(project),
        stage=_label(stage),
        start_at=start_at,
    )
    db.add(task)
    db.flush()  # the timeline row below points at the task
    activity.record(db, actor, task, "created", new="todo")


def update_task(db: Session, actor: Person, task_id: uuid.UUID, changes: dict, today: date | None = None) -> None:
    """`changes` holds only the fields the client sent (TaskUpdate.model_dump(exclude_unset=True)).
    Content edits and a new assignee are separate timeline entries, one per field that really changed."""
    task, team = get_task_and_team(db, task_id, lock=True)
    authorization.require_act(actor, team)
    if task.status == "done":
        raise AppError("task_done", "A finished task cannot be edited. Reopen it first.", 409)
    if changes.get("due_at") != task.due_at:  # keeping an old date that has since passed is fine; choosing a past one is not
        _require_not_past(changes.get("due_at"), today)
    new_assignee = None
    if changes.get("assignee_id") not in (None, task.assignee_id):
        new_assignee = _assignee_on(db, team, changes["assignee_id"])

    edits = []  # (field label, old, new)
    for field, label, value in (
        ("title", states.FIELD_TITLE, _clean_title(changes["title"]) if changes.get("title") is not None else None),
        ("description", states.FIELD_DESCRIPTION, changes["description"].strip() if changes.get("description") is not None else None),
        ("priority", states.FIELD_PRIORITY, changes.get("priority")),
    ):
        if value is not None and value != getattr(task, field):
            edits.append((label, getattr(task, field), value))
            setattr(task, field, value)
    if "due_at" in changes and changes["due_at"] != task.due_at:  # null is a real change: it clears the date
        edits.append((states.FIELD_DUE, task.due_at, changes["due_at"]))
        task.due_at = changes["due_at"]
    if "start_at" in changes and changes["start_at"] != task.start_at:
        edits.append((states.FIELD_START, task.start_at, changes["start_at"]))
        task.start_at = changes["start_at"]
    _require_start_not_after_due(task.start_at, task.due_at)
    for field, label in (("project", states.FIELD_PROJECT), ("stage", states.FIELD_STAGE)):
        if field in changes and _label(changes[field]) != getattr(task, field):
            edits.append((label, getattr(task, field), _label(changes[field])))
            setattr(task, field, _label(changes[field]))
    if "support_id" in changes and changes["support_id"] != task.support_id:  # null clears it
        old_support = get_person(db, task.support_id) if task.support_id else None
        new_support = _support(db, changes["support_id"]) if changes["support_id"] else None
        edits.append((
            states.FIELD_SUPPORT, old_support.name if old_support else None, new_support.name if new_support else None,
        ))
        task.support_id = new_support.id if new_support else None
    for label, old, new in edits:
        activity.record(db, actor, task, "edit", field=label, old=_text(old), new=_text(new))

    if new_assignee is not None:
        old_assignee = get_person(db, task.assignee_id) if task.assignee_id else None
        activity.record(
            db, actor, task, "reassign",
            field=states.FIELD_ASSIGNEE, old=old_assignee.name if old_assignee else None, new=new_assignee.name,
        )
        audit.record(
            db, actor, identity_states.TASK_REASSIGN, team_id=team.id, person_id=new_assignee.id,
            details={
                "task_id": str(task.id), "title": task.title,
                "from": old_assignee.name if old_assignee else None, "to": new_assignee.name,
            },
        )
        task.assignee_id = new_assignee.id
    db.commit()


def delete_task(db: Session, actor: Person, task_id: uuid.UUID) -> None:
    task, team = get_task_and_team(db, task_id, lock=True)
    authorization.require_act(actor, team)
    if not authorization.can_delete_task(actor, team, task.status):
        raise AppError("not_deletable", "A task can be deleted only while it is To Do or In Progress.", 409)
    # The task's timeline is removed with it, so what it held is kept in the append-only audit log first.
    record_task_deleted(db, actor, task)
    db.delete(task)
    db.commit()


def move_task(
    db: Session,
    actor: Person,
    task_id: uuid.UUID,
    to: str,
    note: str | None,
    completed_on: date | None = None,
    today: date | None = None,
) -> None:
    """Move a card. Every move is on the timeline with its actor; a reason (remarks for Done) is stored with it.
    Moving to Done may name the day the work really finished (`completed_on`: from the due date, once it has passed, up to today)
    so reports stay true when the card was moved late; the due date is not touched. `today` is for tests."""
    task, team = get_task_and_team(db, task_id, lock=True)
    authorization.require_act(actor, team)
    move = authorization.transition_to(actor, team, task.status, to)
    if move is None:
        raise AppError("invalid_transition", f"A task cannot move from {task.status} to {to}.", 409)
    note_text = (note or "").strip()
    if move.needs_reason and not note_text:
        message = "Remarks are required to mark a task Done." if to == "done" else "A reason is required for this change."
        raise AppError("reason_required", message, 422)
    today = today or date.today()
    if completed_on is not None and to != "done":
        raise AppError("completed_on_not_done", "A completion date applies only when marking a task Done.", 422)
    if completed_on is not None and completed_on > today:
        raise AppError("completed_on_invalid", "The completion date cannot be in the future.", 422)
    if completed_on is not None and task.due_at is not None and task.due_at <= today and completed_on < task.due_at:
        raise AppError("completed_on_invalid", "The completion date cannot be before the due date.", 422)
    old_status = task.status
    task.status = to
    task.closed_at = None
    if to == "done":
        late = completed_on is not None and completed_on != today
        # An earlier day is stored at midday local time so every day-based report reads it as that day.
        task.closed_at = datetime.combine(completed_on, time(12)).astimezone() if late else datetime.now(timezone.utc)
        if late:
            note_text = f"{note_text}\n(Completed on {completed_on.isoformat()})"
    if move.kind == "send_back":
        task.returned_count += 1
    activity.record(db, actor, task, "status", field=states.FIELD_STATUS, old=old_status, new=to, note=note_text or None)
    db.commit()


def add_comment(db: Session, actor: Person, task_id: uuid.UUID, entry_id: uuid.UUID, body: str) -> None:
    task, team = get_task_and_team(db, task_id, lock=True)
    authorization.require_view_team(actor, team)  # the team's manager or any admin
    if not authorization.can_comment(actor, team, task.status):
        raise AppError("task_done", "A finished task takes no comments; reopen it first.", 409)
    text = body.strip()
    if not text:
        raise AppError("comment_required", "Write a comment first.", 422)
    activity.record(db, actor, task, "comment", entry_id=entry_id, note=text)
    task.updated_at = datetime.now(timezone.utc)
    db.commit()


# ---- rules ----

def _require_not_past(due_at: date | None, today: date | None) -> None:
    """A due date is today or later (no date at all is fine). `today` is the server's date; tests pass their own."""
    if due_at is not None and due_at < (today or date.today()):
        raise AppError("due_date_past", "The due date cannot be in the past.", 422)


def _require_start_not_after_due(start_at: date | None, due_at: date | None) -> None:
    if start_at is not None and due_at is not None and start_at > due_at:
        raise AppError("start_after_due", "The start date cannot be after the due date.", 422)


def _label(value: str | None) -> str | None:
    """Project and stage are free text; blank means none."""
    return (value or "").strip() or None


def _support(db: Session, person_id: uuid.UUID) -> Person:
    """Support may be anyone active in the directory; the task still lives only on the assignee's team."""
    person = get_person(db, person_id)
    if not person.active:
        raise AppError("invalid_support", "Choose an active person for support.", 422)
    return person


def _clean_title(title: str) -> str:
    text = title.strip()
    if not text:
        raise AppError("title_required", "A title is required.", 422)
    return text


def _assignee_on(db: Session, team: Team, person_id: uuid.UUID) -> Person:
    """The task's owner must be an active person on the team (the manager counts)."""
    person = get_person(db, person_id)
    if not person.active or person.team_id != team.id:
        raise AppError("invalid_assignee", "Choose an active person on your team.", 422)
    return person


def _text(value: object) -> str | None:
    return None if value is None else str(value)
