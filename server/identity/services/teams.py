"""Teams and who runs them.

Commands (create_team, change_manager, delete_team) change data, commit once, and return nothing.
Queries (list_teams, get_team_with_count) only read.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity import states
from identity.services import audit
from identity.services.lookup import get_person, get_team
from models import ROLE_MANAGER, ROLE_MEMBER, Person, Task, Team
from security.authorization import is_admin, require_admin
from tasks.services.deletion_audit import record_task_deleted


# ---- queries ----

def list_teams(db: Session, actor: Person) -> list[tuple[Team, int]]:
    """Admins see every team; a manager sees only the team they run. Each team comes with its headcount."""
    query = select(Team).order_by(func.lower(Team.name))
    if not is_admin(actor):
        query = query.where(Team.manager_id == actor.id)
    teams = list(db.scalars(query).unique())
    counts = dict(
        db.execute(
            select(Person.team_id, func.count())
            .where(Person.team_id.in_([team.id for team in teams]))
            .group_by(Person.team_id)
        ).all()
    )
    return [(team, counts.get(team.id, 0)) for team in teams]


def get_team_with_count(db: Session, team_id: uuid.UUID) -> tuple[Team, int]:
    team = get_team(db, team_id)
    count = db.scalar(select(func.count()).select_from(Person).where(Person.team_id == team.id))
    return team, count or 0


# ---- commands ----

def create_team(
    db: Session, actor: Person, team_id: uuid.UUID, name: str, initial_person_id: uuid.UUID, reason: str
) -> None:
    """New team plus its first person, who becomes the manager, in one transaction.

    The caller supplies team_id so it can read the team back with get_team_with_count."""
    require_admin(actor)
    reason_text = audit.clean_reason(reason, required=True)
    name = name.strip()
    if not name:
        raise AppError("name_required", "Give the team a name.", 422)
    person = get_person(db, initial_person_id, lock=True)
    _check_can_run(person)

    team = Team(id=team_id, name=name)
    db.add(team)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError("team_name_taken", "A team with that name already exists.", 409)

    person.team_id = team_id
    _promote(person)
    team.manager_id = person.id
    audit.record(
        db, actor, states.TEAM_CREATE, team_id=team_id, person_id=person.id, reason=reason_text,
        details={"name": name, "manager_id": str(person.id)},
    )
    db.commit()


def change_manager(db: Session, actor: Person, team_id: uuid.UUID, new_person_id: uuid.UUID, reason: str) -> None:
    """Make another person the team's manager. The previous manager stays on the team as a plain member."""
    require_admin(actor)
    reason_text = audit.clean_reason(reason, required=True)
    team = get_team(db, team_id, lock=True)
    new_manager = get_person(db, new_person_id, lock=True)
    if new_manager.id == team.manager_id:
        raise AppError("same_manager", "That person already manages this team.", 409)
    _check_can_run(new_manager, team)

    old_manager_id = team.manager_id
    if old_manager_id is not None:
        _demote(get_person(db, old_manager_id, lock=True))
        # Flush the demotion first: a partial unique index allows one manager-role person per team.
        db.flush()
    new_manager.team_id = team.id
    _promote(new_manager)
    team.manager_id = new_manager.id
    audit.record(
        db, actor, states.TEAM_MANAGER_CHANGE, team_id=team.id, person_id=new_manager.id, reason=reason_text,
        details={
            "old_manager_id": str(old_manager_id) if old_manager_id else None,
            "new_manager_id": str(new_manager.id),
        },
    )
    db.commit()


def delete_team(db: Session, actor: Person, team_id: uuid.UUID, confirm_name: str, reason: str) -> None:
    """Erase a team for good. Its people go back to no team and the manager goes back to member.

    Irreversible, so the caller must repeat the team's name. The audit log keeps one row about the deletion
    (name, who was on it); everything else belonging to the team is deleted with it."""
    require_admin(actor)
    reason_text = audit.clean_reason(reason, required=True)
    team = get_team(db, team_id, lock=True)
    if confirm_name.strip().lower() != team.name.lower():
        raise AppError("confirmation_mismatch", "Type the team's name exactly to delete it.", 422)

    members = list(db.scalars(select(Person).where(Person.team_id == team.id).with_for_update(of=Person)).unique())
    details = {
        "name": team.name,
        "manager_id": str(team.manager_id) if team.manager_id else None,
        "member_ids": [str(person.id) for person in members],
    }
    for person in members:
        person.team_id = None
        _demote(person)
    db.flush()
    # The team's tasks go with it, so each keeps its own snapshot in the audit log, as a single task delete does.
    for team_task in db.scalars(select(Task).where(Task.team_id == team.id).order_by(Task.created_at, Task.id)):
        record_task_deleted(db, actor, team_task, reason_text)
    audit.record(db, actor, states.TEAM_DELETE, team_id=team.id, reason=reason_text, details=details)
    db.delete(team)
    db.commit()


# ---- rules ----

def _check_can_run(person: Person, team: Team | None = None) -> None:
    """Who may be made a team's manager: an active member (admin or not) on no team, or already on this one."""
    if not person.active:
        raise AppError("person_inactive", "That person is inactive.", 409)
    if person.role == ROLE_MANAGER:
        raise AppError("already_manager", "That person already manages a team.", 409)
    if person.team_id is not None and (team is None or person.team_id != team.id):
        raise AppError("already_on_team", "That person is already on another team. Remove them from it first.", 409)


def _promote(person: Person) -> None:
    person.role = ROLE_MANAGER


def _demote(person: Person) -> None:
    person.role = ROLE_MEMBER
