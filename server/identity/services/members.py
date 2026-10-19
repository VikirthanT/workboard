"""People on a team.

Commands (add_member, remove_member) change data, commit once, and return nothing.
Queries (list_members, get_member) only read.

Who may act: an admin on any team, a manager on the team they run (security.authorization).
A reason is required from an admin and optional from a manager.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity import states
from identity.services import audit
from identity.services.lookup import get_person, get_team
from models import ROLE_MANAGER, Person, Task, Team
from security.authorization import is_admin, require_team_access


# ---- queries ----

def list_members(db: Session, actor: Person, team_id: uuid.UUID) -> list[Person]:
    """Everyone on the team, the manager first. The manager is an assignee like the rest."""
    team = get_team(db, team_id)
    require_team_access(actor, team)
    query = (
        select(Person)
        .where(Person.team_id == team.id)
        .order_by((Person.role == ROLE_MANAGER).desc(), Person.name)
    )
    return list(db.scalars(query).unique())


def open_task_counts(db: Session, people: list[Person]) -> dict[uuid.UUID, int]:
    """How many tasks each of these people holds that are not Done. One query; people with none are left out."""
    return dict(
        db.execute(
            select(Task.assignee_id, func.count())
            .where(Task.assignee_id.in_([p.id for p in people]), Task.status != "done")
            .group_by(Task.assignee_id)
        ).all()
    )


def get_member(db: Session, team_id: uuid.UUID, person_id: uuid.UUID) -> Person:
    person = get_person(db, person_id)
    if person.team_id != team_id:
        raise AppError("not_on_team", "That person is not on this team.", 404)
    return person


# ---- commands ----

def add_member(db: Session, actor: Person, team_id: uuid.UUID, person_id: uuid.UUID, reason: str | None) -> None:
    team = get_team(db, team_id)
    require_team_access(actor, team)
    reason_text = audit.clean_reason(reason, required=False)  # adding is routine: optional for admins too
    person = get_person(db, person_id, lock=True)
    if not person.active:
        raise AppError("person_inactive", "That person is inactive.", 409)
    if person.team_id is not None:
        raise AppError("already_on_team", "That person is already on a team.", 409)
    if person.role == ROLE_MANAGER:
        raise AppError("person_unavailable", "Managers cannot be added as members.", 409)
    person.team_id = team.id
    audit.record(db, actor, states.MEMBER_ADD, team_id=team.id, person_id=person.id, reason=reason_text)
    db.commit()


def remove_member(db: Session, actor: Person, team_id: uuid.UUID, person_id: uuid.UUID, reason: str | None) -> None:
    """Take a person off the team (the dustbin). Their open tasks are left as they are: once tasks exist, a task
    whose assignee is no longer on the task's team is the one that "needs a new owner", so nothing is stored here."""
    person, team, reason_text = _prepare_change(db, actor, team_id, person_id, reason)
    person.team_id = None
    audit.record(db, actor, states.MEMBER_REMOVE, team_id=team.id, person_id=person.id, reason=reason_text)
    db.commit()


# ---- rules ----

def _reason_for(actor: Person, reason: str | None) -> str | None:
    return audit.clean_reason(reason, required=is_admin(actor))


def _prepare_change(
    db: Session, actor: Person, team_id: uuid.UUID, person_id: uuid.UUID, reason: str | None
) -> tuple[Person, Team, str | None]:
    """Checks before taking someone off a team: access, reason, they are on it, and they are not the manager."""
    team = get_team(db, team_id)
    require_team_access(actor, team)
    reason_text = _reason_for(actor, reason)
    person = get_person(db, person_id, lock=True)
    if person.team_id != team.id:
        raise AppError("not_on_team", "That person is not on this team.", 404)
    if person.id == team.manager_id:
        raise AppError("is_manager", "Change the team's manager first; the manager cannot be removed or deactivated.", 409)
    return person, team, reason_text
