"""Who is an admin. The toggle in the admin panel ("Make admin" / "Revoke admin").

set_admin is a command: it changes data, commits once, and returns nothing. It never touches role or team_id,
so a member or manager keeps their place on their team while gaining or losing admin.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity import states
from identity.services import audit
from identity.services.lookup import get_person
from models import Person
from security.authorization import require_admin


def set_admin(db: Session, actor: Person, person_id: uuid.UUID, make_admin: bool, reason: str) -> None:
    require_admin(actor)
    reason_text = audit.clean_reason(reason, required=True)
    # A revoke locks every active admin first, in id order, and only then the person. Locking the person first let two
    # admins revoking each other deadlock (each held one row and waited for the other's), which was a 500.
    active_admins = _lock_active_admins(db) if not make_admin else []
    person = get_person(db, person_id, lock=True)
    if person.is_admin == make_admin:
        state = "already an admin" if make_admin else "not an admin"
        raise AppError("admin_unchanged", f"That person is {state}.", 409)
    if make_admin and not person.active:
        raise AppError("person_inactive", "An inactive person cannot be made an admin.", 409)
    if not make_admin:
        _require_another_admin(active_admins, person)

    person.is_admin = make_admin
    action = states.ADMIN_GRANT if make_admin else states.ADMIN_REVOKE
    audit.record(db, actor, action, person_id=person.id, reason=reason_text)
    db.commit()


def _lock_active_admins(db: Session) -> list[Person]:
    """Every active admin, row-locked so two admins revoking each other at the same moment cannot both pass the
    last-admin check. Always in id order, so two callers never wait on each other in a circle."""
    return list(db.scalars(
        select(Person).where(Person.is_admin.is_(True), Person.active.is_(True)).order_by(Person.id).with_for_update(of=Person)
    ))


def _require_another_admin(active_admins: list[Person], leaving: Person) -> None:
    """Refuse a revoke that would leave nobody able to use the admin panel."""
    if not any(admin.id != leaving.id for admin in active_admins):
        raise AppError("last_admin", "There must be at least one active admin.", 409)
