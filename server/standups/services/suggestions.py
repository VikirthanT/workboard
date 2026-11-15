"""What a manager does with a suggestion: edit it, reject it, restore it, or add it to the board.

Commands: each checks who is asking, writes, commits once and returns nothing. Only adding creates tasks, and it is
all or nothing: if one suggestion breaks a task rule (a due date in the past, an assignee who left), none is added.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity.services.lookup import get_team
from models import Person, TaskSuggestion, Team
from models.tasks import PRIORITIES
from security.authorization import require_act
from standups.llm.extract import norm
from standups.states import KEEP_DAYS
from tasks import states as task_states
from tasks.services.commands import add_task_uncommitted, require_not_past, require_start_not_after_due

EDITABLE = ("title", "description", "priority", "person_id", "start_at", "due_at")


def edit_suggestion(db: Session, actor: Person, suggestion_id: uuid.UUID, changes: dict) -> None:
    """Change a pending suggestion. Setting the due date makes it the manager's own, no longer the default."""
    suggestion, team = _pending(db, actor, suggestion_id)
    for field, value in changes.items():
        if field not in EDITABLE:
            continue
        if field == "title":
            value = (value or "").strip()
            if not value or len(value) > task_states.MAX_TITLE_LENGTH:
                raise AppError("invalid_title", "Give the task a short title.", 422)
            suggestion.title_key = norm(value)
        elif field == "description":
            value = (value or "").strip()
            if not value or len(value) > task_states.MAX_DESCRIPTION_LENGTH:
                raise AppError("invalid_description", "Describe what done looks like.", 422)
        elif field == "priority" and value not in PRIORITIES:
            raise AppError("invalid_priority", "Priority must be low, medium or high.", 422)
        elif field == "person_id":
            person = db.get(Person, value)
            if person is None or person.team_id != team.id or not person.active:
                raise AppError("invalid_assignee", "Choose an active person on this team.", 422)
        elif field == "due_at":
            require_not_past(value)  # the same rule a task has: choosing a past date is refused, clearing it is fine
            suggestion.due_is_default = False
        setattr(suggestion, field, value)
    require_start_not_after_due(suggestion.start_at, suggestion.due_at)
    db.commit()


def reject_suggestion(db: Session, actor: Person, suggestion_id: uuid.UUID) -> None:
    suggestion, _ = _pending(db, actor, suggestion_id)
    suggestion.state, suggestion.state_at = "rejected", _now()
    db.commit()


def restore_suggestion(db: Session, actor: Person, suggestion_id: uuid.UUID) -> None:
    """Bring a rejected suggestion back, while it is still kept."""
    suggestion, team = _get(db, suggestion_id)
    require_act(actor, team)
    if suggestion.state != "rejected" or suggestion.state_at < _now() - timedelta(days=KEEP_DAYS):
        raise AppError("not_restorable", f"Only a suggestion rejected in the last {KEEP_DAYS} days can be restored.", 409)
    suggestion.state, suggestion.state_at = "pending", _now()
    db.commit()


def add_to_board(
    db: Session,
    actor: Person,
    team_id: uuid.UUID,
    suggestion_ids: list[uuid.UUID],
    due_dates: dict[uuid.UUID, date] | None = None,
) -> None:
    """Create a task from each chosen pending suggestion, assigned to the person it is for, and mark them approved.

    A task made this way must have a due date. A suggestion that has none (or whose date the manager changes) gets it from
    `due_dates`, keyed by suggestion id; if any chosen suggestion still has no date, nothing is added and the error names it.
    The date is stored on the suggestion, as the manager's own rather than a default."""
    team = get_team(db, team_id)
    require_act(actor, team)
    ids = list(dict.fromkeys(suggestion_ids))
    due_dates = due_dates or {}
    if not set(due_dates) <= set(ids):
        raise AppError("invalid_due_dates", "A due date was given for a suggestion that is not being added.", 422)
    chosen = list(db.scalars(
        select(TaskSuggestion).where(TaskSuggestion.id.in_(ids), TaskSuggestion.team_id == team.id)
        .order_by(TaskSuggestion.created_at, TaskSuggestion.title).with_for_update()
    ))
    if len(chosen) != len(ids):
        raise AppError("suggestion_not_found", "One of those suggestions no longer exists.", 404)
    if any(s.state != "pending" for s in chosen):
        raise AppError("suggestion_not_pending", "One of those suggestions has already been added or rejected.", 409)
    for s in chosen:  # every date is settled before anything is created, so a missing one adds nothing
        due = due_dates.get(s.id, s.due_at)
        if due is None:
            raise AppError("due_date_required", f"“{s.title}”: choose a due date. A task needs one.", 422)
        if due != s.due_at:
            s.due_at, s.due_is_default = due, False
    for s in chosen:
        task_id = uuid.uuid4()
        description = s.description + ("\n\nParts:\n" + "\n".join(f"- {part}" for part in s.subtasks) if s.subtasks else "")
        # A start date later than the due date breaks a task rule, so the start is dropped rather than refusing the task.
        start = s.start_at if s.due_at is None or s.start_at is None or s.start_at <= s.due_at else None
        try:
            add_task_uncommitted(db, actor, team, task_id, s.title, description, s.priority, s.due_at, s.person_id, start)
        except AppError as err:
            db.rollback()
            who = db.get(Person, s.person_id)
            if err.code == "invalid_assignee" and who is not None:  # say who, not just "your team"
                raise AppError(err.code, f"“{s.title}”: {who.name} is no longer an active member of this team. Reassign or reject this suggestion.", err.status_code) from err
            raise AppError(err.code, f"“{s.title}”: {err.message}", err.status_code) from err
        s.state, s.state_at, s.task_id = "approved", _now(), task_id
    db.commit()


def expire(db: Session, team_id: uuid.UUID) -> None:
    """Remove pending suggestions that were never reviewed, and rejected ones, once KEEP_DAYS have passed. A removed
    suggestion does not come back: its submission is already recorded as read."""
    cutoff = _now() - timedelta(days=KEEP_DAYS)
    db.execute(delete(TaskSuggestion).where(
        TaskSuggestion.team_id == team_id,
        TaskSuggestion.state_at < cutoff,
        or_(TaskSuggestion.state == "pending", TaskSuggestion.state == "rejected"),
    ))
    db.commit()


def delete_older_uncommitted(db: Session, team_id: uuid.UUID, person_id: uuid.UUID, standup_date: date) -> None:
    """A newer standup replaces what the person's older ones proposed: their pending and rejected suggestions from
    earlier standups are removed. Approved ones stay, they are the link from a task back to its standup. The caller
    commits, so the clean-up and the new suggestions land together or not at all."""
    db.execute(delete(TaskSuggestion).where(
        TaskSuggestion.team_id == team_id,
        TaskSuggestion.person_id == person_id,
        TaskSuggestion.standup_date < standup_date,
        TaskSuggestion.state.in_(("pending", "rejected")),
    ))


def _get(db: Session, suggestion_id: uuid.UUID) -> tuple[TaskSuggestion, Team]:
    suggestion = db.scalar(select(TaskSuggestion).where(TaskSuggestion.id == suggestion_id).with_for_update())
    if suggestion is None:
        raise AppError("suggestion_not_found", "That suggestion no longer exists.", 404)
    return suggestion, get_team(db, suggestion.team_id)


def _pending(db: Session, actor: Person, suggestion_id: uuid.UUID) -> tuple[TaskSuggestion, Team]:
    suggestion, team = _get(db, suggestion_id)
    require_act(actor, team)
    if suggestion.state != "pending":
        raise AppError("suggestion_not_pending", "That suggestion has already been added or rejected.", 409)
    return suggestion, team


def _now() -> datetime:
    return datetime.now(timezone.utc)
