import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity.states import MAX_REASON_LENGTH
from models import AccessAuditLog, Person, Team
from security.authorization import require_admin


def clean_reason(reason: str | None, *, required: bool) -> str | None:
    text = (reason or "").strip()
    if required and not text:
        raise AppError("reason_required", "Give a reason for this change.", 422)
    if len(text) > MAX_REASON_LENGTH:
        raise AppError("reason_too_long", f"Keep the reason under {MAX_REASON_LENGTH} characters.", 422)
    return text or None


def record(
    db: Session,
    actor: Person,
    action: str,
    *,
    team_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    """Adds the row to the caller's transaction; the caller commits."""
    db.add(
        AccessAuditLog(
            actor_id=actor.id, action=action, team_id=team_id, person_id=person_id, reason=reason, details=details
        )
    )


def names_for(db: Session, entries: list[AccessAuditLog]) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    """Current names of the people and teams these entries mention, for showing them. Two queries, whatever the page size."""
    person_ids = {i for e in entries for i in (e.actor_id, e.person_id) if i}
    team_ids = {e.team_id for e in entries if e.team_id}
    people = dict(db.execute(select(Person.id, Person.name).where(Person.id.in_(person_ids))).all()) if person_ids else {}
    teams = dict(db.execute(select(Team.id, Team.name).where(Team.id.in_(team_ids))).all()) if team_ids else {}
    return people, teams


def list_entries(db: Session, actor: Person, *, limit: int, offset: int) -> tuple[list[AccessAuditLog], int]:
    """One page of the log, newest first, and the total number of entries. Admins only."""
    require_admin(actor)
    total = db.scalar(select(func.count()).select_from(AccessAuditLog)) or 0
    # Rows written in one transaction share a timestamp, so id breaks the tie and keeps pages stable.
    page = (
        select(AccessAuditLog)
        .order_by(AccessAuditLog.created_at.desc(), AccessAuditLog.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(page)), total
