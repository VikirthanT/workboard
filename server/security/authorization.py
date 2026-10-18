"""What a signed-in person may do. Mirrors client/src/app/domain/permissions.ts; keep the two in step."""
from typing import NamedTuple

from core.exceptions import AppError
from models import ROLE_MANAGER, Person, Team


def is_admin(person: Person) -> bool:
    return person.is_admin


def can_login(person: Person) -> bool:
    """Only active managers and admins sign in. Everyone else in the directory is an assignee."""
    return person.active and (person.is_admin or person.role == ROLE_MANAGER)


def require_admin(actor: Person) -> None:
    if not is_admin(actor):
        raise AppError("forbidden", "Only an admin can do this.", 403)


def can_manage_team(actor: Person, team: Team) -> bool:
    """Membership changes: an admin on any team, a manager on the team they run.

    Board actions (create, move) are a separate, stricter rule below: admins only read boards they do not run."""
    return is_admin(actor) or team.manager_id == actor.id


def require_team_access(actor: Person, team: Team) -> None:
    if not can_manage_team(actor, team):
        raise AppError("forbidden", "You can only manage your own team.", 403)


# ---- boards and tasks: stricter than membership. An admin reads every board but acts only on the team they run ----

DELETABLE_STATUSES = ("todo", "in_progress")


class Transition(NamedTuple):
    to: str
    kind: str
    label: str  # the button text, as in client permissions.ts
    needs_reason: bool  # a reason, or for Done the remarks; always stored on the timeline entry


# from status -> {to status: (kind, label, needs_reason)}. Every road into Done needs remarks.
_TRANSITIONS: dict[str, dict[str, tuple[str, str, bool]]] = {
    "todo": {
        "in_progress": ("start", "Move to In Progress", False),
        "blocked": ("block", "Mark blocked", True),
    },
    "in_progress": {
        "review": ("submit", "Move to Review", False),
        "done": ("complete", "Mark done", True),
        "blocked": ("block", "Mark blocked", True),
        "todo": ("move_back", "Move back to To Do", True),
    },
    "blocked": {
        "in_progress": ("resume", "Resume", False),
        "done": ("complete", "Mark done", True),
        "todo": ("move_back", "Move back to To Do", True),
    },
    "review": {"done": ("accept", "Accept", True), "in_progress": ("send_back", "Send back", True)},
    "done": {"in_progress": ("reopen", "Reopen", True)},
}


def can_view_team(actor: Person, team: Team) -> bool:
    return is_admin(actor) or team.manager_id == actor.id


def can_act(actor: Person, team: Team) -> bool:
    """Create, edit, move, delete and comment: only the team's own manager."""
    return team.manager_id == actor.id


def require_view_team(actor: Person, team: Team) -> None:
    if not can_view_team(actor, team):
        raise AppError("forbidden", "You can only see your own team's board.", 403)


def require_act(actor: Person, team: Team) -> None:
    if not can_act(actor, team):
        raise AppError("forbidden", "Only the team's manager can change its tasks.", 403)


def can_delete_task(actor: Person, team: Team, status: str) -> bool:
    return can_act(actor, team) and status in DELETABLE_STATUSES


def can_comment(actor: Person, team: Team, status: str) -> bool:
    """The team's manager and any admin (on any team's board) may comment, until the task is Done."""
    return can_view_team(actor, team) and status != "done"


def transitions_for(actor: Person, team: Team, status: str) -> list[Transition]:
    if not can_act(actor, team):
        return []
    return [Transition(to, *rest) for to, rest in _TRANSITIONS[status].items()]


def transition_to(actor: Person, team: Team, status: str, to: str) -> Transition | None:
    return next((t for t in transitions_for(actor, team, status) if t.to == to), None)
