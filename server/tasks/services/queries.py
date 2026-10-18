"""Task queries: the board, one task, one task with its timeline. They read and change nothing.

Who may read is decided here (security.authorization): a team's manager, and any admin. Every task comes back
with the `actions` the signed-in person may take, so the UI only shows what the server would allow.

shortcut: the board loads a team's tasks and filters in Python; fine for a team's tens of cards, move the
filters into SQL if a board ever holds thousands.
"""
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity.services.lookup import get_team
from models import Person, Task, TaskActivity, Team
from security import authorization
from tasks import rules, schemas
from tasks.services.lookup import get_task_and_team

FILTERS = ("needs_review", "overdue", "blocked", "due_week")


@dataclass
class _Context:
    """Who and what the response builders need, loaded once for a batch of tasks."""

    people: dict[uuid.UUID, Person]
    last_status: dict[uuid.UUID, TaskActivity]  # task id -> its latest status move


# ---- which team ----

def resolve_board_team(db: Session, actor: Person, team_id: uuid.UUID | None) -> Team:
    """A manager gets their own team and is refused another; an admin may ask for any team, else gets the one they run."""
    own = db.scalar(select(Team).where(Team.manager_id == actor.id))
    if team_id is None or (own is not None and team_id == own.id):
        if own is not None:
            return own
        if authorization.is_admin(actor):
            raise AppError("choose_team", "Choose a team to look at.", 400)
        raise AppError("no_team", "You are not on any team yet. Ask an admin to add you to one.", 403)
    team = get_team(db, team_id)
    authorization.require_view_team(actor, team)
    return team


# ---- one task ----

def get_task(db: Session, actor: Person, task_id: uuid.UUID, today: date | None = None) -> schemas.TaskResponse:
    task, team = get_task_and_team(db, task_id)
    authorization.require_view_team(actor, team)
    context = _load(db, [task])
    return _task_response(task, team, actor, context, today or _today())


def get_task_detail(db: Session, actor: Person, task_id: uuid.UUID, today: date | None = None) -> schemas.TaskDetail:
    task, team = get_task_and_team(db, task_id)
    authorization.require_view_team(actor, team)
    entries = list(db.scalars(select(TaskActivity).where(TaskActivity.task_id == task.id).order_by(TaskActivity.created_at, TaskActivity.id)))
    context = _load(db, [task], extra_people=[e.actor_id for e in entries])
    return schemas.TaskDetail(
        task=_task_response(task, team, actor, context, today or _today()),
        timeline=[_activity_response(e, task, context) for e in entries],
    )


def get_activity(db: Session, actor: Person, entry_id: uuid.UUID) -> schemas.ActivityResponse:
    entry = db.get(TaskActivity, entry_id)
    if entry is None:
        raise AppError("activity_not_found", "That timeline entry does not exist.", 404)
    task, team = get_task_and_team(db, entry.task_id)
    authorization.require_view_team(actor, team)
    return _activity_response(entry, task, _load(db, [task], extra_people=[entry.actor_id]))


# ---- the board ----

def get_board(
    db: Session,
    actor: Person,
    team: Team,
    *,
    person_id: uuid.UUID | None = None,
    filters: list[str] | None = None,
    attention: bool = False,
    today: date | None = None,
) -> schemas.Board:
    """`team` comes from resolve_board_team, which has already checked the actor may read it."""
    filters = filters or []
    unknown = [f for f in filters if f not in FILTERS]
    if unknown:
        raise AppError("unknown_filter", f"Unknown filter: {unknown[0]}.", 422)
    today = today or _today()

    # Open cards in the order they were made; Done cards stay on the board, the most recently closed first.
    visible = list(db.scalars(select(Task).where(Task.team_id == team.id, Task.status != "done").order_by(Task.created_at, Task.id)))
    visible += db.scalars(
        select(Task).where(Task.team_id == team.id, Task.status == "done").order_by(Task.closed_at.desc(), Task.id)
    )
    context = _load(db, visible)

    def assignee(task: Task) -> Person | None:
        return context.people.get(task.assignee_id)  # None when unassigned

    scoped = [t for t in visible if person_id is None or t.assignee_id == person_id]
    attention_tasks = [t for t in scoped if rules.needs_attention(t, assignee(t), today)]
    in_view = attention_tasks if attention else scoped
    matches = {
        "overdue": lambda t: rules.is_overdue(t, today),
        "due_week": lambda t: rules.is_due_this_week(t, today),
        "blocked": lambda t: t.status == "blocked",
        "needs_review": lambda t: t.status == "review",
    }
    shown = [t for t in in_view if all(matches[f](t) for f in filters)]
    members = db.scalars(select(Person).where(Person.team_id == team.id, Person.active).order_by(Person.name))

    def build(tasks: list[Task]) -> list[schemas.TaskResponse]:
        return [_task_response(t, team, actor, context, today) for t in tasks]

    return schemas.Board(
        team=schemas.BoardTeam(id=team.id, name=team.name, manager=_summary(team.manager)),
        read_only=not authorization.can_act(actor, team),
        tasks=build(shown),
        people=[_summary(p) for p in members],
        filter_counts={f: sum(1 for t in in_view if matches[f](t)) for f in FILTERS},
        attention_count=len(attention_tasks),
        stats=schemas.BoardStats(
            todo=sum(t.status == "todo" for t in scoped),
            in_progress=sum(t.status == "in_progress" for t in scoped),
            blocked=sum(t.status == "blocked" for t in scoped),
            overdue=sum(rules.is_overdue(t, today) for t in scoped),
            done=sum(t.status == "done" for t in scoped),
        ),
        orphans=build([t for t in visible if rules.needs_reassignment(t, assignee(t))]),
    )


# ---- shaping ----

def _today() -> date:
    return date.today()


def _summary(person: Person | None) -> schemas.PersonSummary | None:
    if person is None:
        return None
    return schemas.PersonSummary(id=person.id, name=person.name, email=person.email, active=person.active)


def _load(db: Session, tasks: list[Task], extra_people: list[uuid.UUID | None] | None = None) -> _Context:
    ids = [t.id for t in tasks]
    status_moves = db.scalars(
        select(TaskActivity)
        .where(TaskActivity.task_id.in_(ids), TaskActivity.kind == "status")
        .order_by(TaskActivity.created_at, TaskActivity.id)
    )
    last_status = {move.task_id: move for move in status_moves}  # later moves overwrite earlier ones
    people_ids = {pid for t in tasks for pid in (t.creator_id, t.assignee_id) if pid}
    people_ids |= {m.actor_id for m in last_status.values() if m.actor_id}
    people_ids |= {pid for pid in (extra_people or []) if pid}
    people = {p.id: p for p in db.scalars(select(Person).where(Person.id.in_(people_ids)))}
    return _Context(people=people, last_status=last_status)


def _latest_reason(task: Task, context: _Context) -> schemas.LatestReason | None:
    move = context.last_status.get(task.id)
    if move is None or not move.note:
        return None
    if task.status == "blocked" and move.new_value == "blocked":
        kind = "blocked"
    elif task.status == "in_progress" and move.old_value == "review":
        kind = "sent_back"
    elif task.status == "in_progress" and move.old_value == "done":
        kind = "reopened"
    else:
        return None
    actor = context.people.get(move.actor_id)
    return schemas.LatestReason(kind=kind, note=move.note, at=move.created_at, actor_name=actor.name if actor else None)


def _actions(actor: Person, team: Team, task: Task) -> schemas.TaskActions:
    acts = authorization.can_act(actor, team)
    return schemas.TaskActions(
        can_edit=acts and task.status != "done",
        can_delete=authorization.can_delete_task(actor, team, task.status),
        can_change_assignee=acts and task.status != "done",
        can_comment=authorization.can_comment(actor, team, task.status),
        transitions=[schemas.TransitionResponse(**t._asdict()) for t in authorization.transitions_for(actor, team, task.status)],
    )


def _task_response(task: Task, team: Team, actor: Person, context: _Context, today: date) -> schemas.TaskResponse:
    reason = _latest_reason(task, context)
    assignee = context.people.get(task.assignee_id)
    return schemas.TaskResponse(
        id=task.id,
        team_id=task.team_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        creator=_summary(context.people.get(task.creator_id)),
        assignee=_summary(assignee),
        returned_count=task.returned_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
        closed_at=task.closed_at,
        overdue=rules.is_overdue(task, today),
        due_soon=rules.is_due_soon(task, today),
        needs_reassignment=rules.needs_reassignment(task, assignee),
        returned=reason is not None and reason.kind == "sent_back",
        latest_reason=reason,
        actions=_actions(actor, team, task),
    )


def _activity_response(entry: TaskActivity, task: Task, context: _Context) -> schemas.ActivityResponse:
    return schemas.ActivityResponse(
        id=entry.id,
        task_id=entry.task_id,
        task_title=task.title,
        actor=_summary(context.people.get(entry.actor_id)),
        kind=entry.kind,
        source=entry.source,
        field=entry.field,
        old_value=entry.old_value,
        new_value=entry.new_value,
        note=entry.note,
        created_at=entry.created_at,
    )
