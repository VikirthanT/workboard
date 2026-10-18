"""People endpoints: who I am, the directory, the admin switch, and the audit log.

A router only does three things: read the request, call one service function, shape the reply. The rules
(who may do this, what is allowed) live in `identity/services` and `security/authorization.py`, not here, so the
same rule applies however the service is reached.

Every endpoint needs a signed-in person (`get_current_person`): anyone else gets 401. Errors always come back as
{"detail": {"code", "message"}}; the codes are listed in `identity/README.md`.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.config import get_db
from identity import schemas
from identity.states import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from identity.services import admin_access, audit, directory
from identity.services.lookup import get_person
from models import Person
from security.authentication import get_current_person

router = APIRouter(tags=["people"])


@router.get("/me", response_model=schemas.PersonResponse)
def me(actor: Person = Depends(get_current_person)):
    """Who is signed in: name, email, role (member or manager), whether they are an admin, and their team.

    Who: any signed-in person. Only active managers and admins get this far; a plain team member is refused at
    sign-in with 403 `not_onboarded`, because team members are assignees, not users.
    """
    return actor


@router.get("/people", response_model=schemas.Page[schemas.PersonResponse])
def list_people(
    unassigned: bool = False,
    admins: bool = False,
    q: str | None = None,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _actor: Person = Depends(get_current_person),
):
    """One page of the people directory, for the "Add person" and "Add admin" pickers and the admins list.

    Who: any signed-in person.
    Query: `unassigned=true` keeps only active people who are on no team (managers are never offered);
    `admins=true` keeps only people with admin access, whether or not they are on a team;
    `q` filters by name or email; `limit` (1 to 200, default 50) and `offset` page through the result.
    Returns: {items, total, limit, offset}. `total` counts every match, not just this page.
    A `limit` or `offset` outside its range is refused with 422; it is never quietly changed.
    """
    people, total = directory.search_people(db, unassigned=unassigned, admins=admins, q=q, limit=limit, offset=offset)
    return schemas.Page(
        items=[schemas.PersonResponse.model_validate(p) for p in people], total=total, limit=limit, offset=offset
    )


@router.patch("/people/{person_id}/admin", response_model=schemas.PersonResponse)
def set_admin(
    person_id: uuid.UUID,
    body: schemas.AdminToggle,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Make someone an admin, or take admin away.

    Who: admins only (403 `forbidden` otherwise).
    Body: {is_admin: true | false, reason}. A reason is required and is written to the audit log.
    Errors: 409 `admin_unchanged` if they already are (or are not) an admin; 409 `last_admin` if this would
    leave the system with no active admin; 404 `person_not_found`.
    Admin is a switch separate from the team role, so a manager can also be an admin.
    """
    admin_access.set_admin(db, actor, person_id, body.is_admin, body.reason)
    return get_person(db, person_id)


@router.get("/audit-log", response_model=schemas.Page[schemas.AuditEntryResponse])
def audit_log(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """One page of the history of team and access changes, newest first.

    Who: admins only (403 `forbidden` otherwise).
    Every team created or deleted, manager change, person added or removed, and admin granted or revoked is here,
    with who did it, to whom, and the reason. The log is append-only: the database itself refuses edits and deletes.
    """
    entries, total = audit.list_entries(db, actor, limit=limit, offset=offset)
    people, teams = audit.names_for(db, entries)
    items = []
    for e in entries:
        item = schemas.AuditEntryResponse.model_validate(e)
        item.actor_name = people.get(e.actor_id)
        item.person_name = people.get(e.person_id)
        # A deleted team keeps its name inside the entry's details.
        item.team_name = teams.get(e.team_id) or (e.details or {}).get("name")
        items.append(item)
    return schemas.Page(items=items, total=total, limit=limit, offset=offset)
