"""Team endpoints: create, list, change the manager, delete, and who is on a team.

A router only reads the request, calls one service function, and shapes the reply. The rules (who may do this,
what is allowed) live in `identity/services/teams.py` and `members.py` and in `security/authorization.py`.
Each handler that changes something runs one command, then one query to build the response.

Every endpoint needs a signed-in person (401 otherwise). Errors come back as {"detail": {"code", "message"}};
the codes are listed in `identity/README.md`. In Phase 1 a team has exactly one manager, a manager runs one team,
and a person is on at most one team.
"""
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database.config import get_db
from identity import schemas
from identity.services import members, teams
from models import Person, Team
from security.authentication import get_current_person

router = APIRouter(prefix="/teams", tags=["teams"])


def _team_response(team: Team, member_count: int) -> schemas.TeamResponse:
    """The team as the API shows it: name, manager (or none yet), and how many people are on it."""
    return schemas.TeamResponse(
        id=team.id,
        name=team.name,
        active=team.active,
        manager=schemas.PersonResponse.model_validate(team.manager) if team.manager else None,
        member_count=member_count,
    )


@router.get("", response_model=list[schemas.TeamResponse])
def list_teams(db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """The teams the caller may see, with their managers and headcounts.

    Who: any signed-in person. An admin sees every team; a manager sees only the team they run.
    Not paged: there are a handful of teams.
    """
    return [_team_response(team, count) for team, count in teams.list_teams(db, actor)]


@router.post("", response_model=schemas.TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(body: schemas.TeamCreate, db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """Create a team and make its first person the manager, in one step.

    Who: admins only (403 `forbidden`).
    Body: {name, initial_manager_person_id, reason}. The reason is required and goes to the audit log.
    The person must be active, on no team, and not already a manager; they become the team's manager.
    Errors: 409 `team_name_taken` (names are unique, ignoring case); 409 `person_inactive`,
    `already_manager` or `already_on_team`; 422 `name_required`; 404 `person_not_found`.
    """
    team_id = uuid.uuid4()
    teams.create_team(db, actor, team_id, body.name, body.initial_manager_person_id, body.reason)
    return _team_response(*teams.get_team_with_count(db, team_id))


@router.patch("/{team_id}/manager", response_model=schemas.TeamResponse)
def change_manager(
    team_id: uuid.UUID,
    body: schemas.ManagerChange,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Make another person the team's manager.

    Who: admins only (403 `forbidden`).
    Body: {person_id, reason}. The old manager is not removed: they stay on the team as a plain member.
    Their open tasks stay with them. Errors: 409 `same_manager` (already the manager), 409 `already_manager`
    (they run another team), `already_on_team`, `person_inactive`; 404 `team_not_found`, `person_not_found`.
    """
    teams.change_manager(db, actor, team_id, body.person_id, body.reason)
    return _team_response(*teams.get_team_with_count(db, team_id))


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: uuid.UUID,
    body: schemas.TeamDelete,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Delete a team for good. This cannot be undone.

    Who: admins only (403 `forbidden`).
    Body: {confirm_name, reason}. `confirm_name` must be the team's name typed exactly (422
    `confirmation_mismatch` otherwise), so a stray click cannot delete a team.
    What happens: the team's tasks and their timelines are erased, its people go back to no team, and its manager
    goes back to being a plain member (an admin keeps admin). The audit log keeps one record of the deletion.
    Returns 204 with no body.
    """
    teams.delete_team(db, actor, team_id, body.confirm_name, body.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{team_id}/members", response_model=list[schemas.PersonResponse])
def list_members(team_id: uuid.UUID, db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """Everyone on the team, the manager first. The manager is an assignee like the rest.

    Who: an admin (any team) or that team's own manager. Anyone else gets 403 `forbidden`.
    Includes people who are no longer in the directory (inactive); they show as inactive.
    """
    return members.list_members(db, actor, team_id)


@router.post("/{team_id}/members", response_model=schemas.PersonResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    team_id: uuid.UUID,
    body: schemas.MemberAdd,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Put a person on the team.

    Who: an admin (any team) or that team's own manager.
    Body: {person_id, reason}. The reason is optional for everyone; if given it goes to the audit log.
    The person must be active and on no team. Managers cannot be added as members.
    Errors: 409 `person_inactive`, `already_on_team`, `person_unavailable`; 404 `person_not_found`.
    """
    members.add_member(db, actor, team_id, body.person_id, body.reason)
    return members.get_member(db, team_id, body.person_id)


@router.delete("/{team_id}/members/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    team_id: uuid.UUID,
    person_id: uuid.UUID,
    body: schemas.MemberRemove | None = None,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Take a person off the team (the dustbin). There is no "inactive" switch: a person is added or removed.

    Who: an admin (any team) or that team's own manager.
    Body (optional): {reason}. An admin must give one (422 `reason_required`); a manager need not.
    Their open tasks are kept, untouched; those tasks then show as needing a new owner.
    The team's manager cannot be removed: change the manager first (409 `is_manager`).
    Returns 204 with no body.
    """
    members.remove_member(db, actor, team_id, person_id, body.reason if body else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
