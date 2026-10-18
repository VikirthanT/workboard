from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models import ROLE_MEMBER, Person


def search_people(
    db: Session, *, unassigned: bool, q: str | None, limit: int, offset: int, admins: bool = False
) -> tuple[list[Person], int]:
    """One page of the Slack-cache directory behind the 'Add person' picker, and the total number of matches.

    Active people only. `unassigned` keeps those on no team; `admins` keeps those with admin access (on a team or not).
    The caller validates limit and offset (see the router)."""
    filters = [Person.active.is_(True)]
    if unassigned:
        filters += [Person.team_id.is_(None), Person.role == ROLE_MEMBER]
    if admins:
        filters.append(Person.is_admin.is_(True))
    term = (q or "").strip()
    if term:
        # % and _ are wildcards in LIKE; escape them so the box searches for exactly what was typed.
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        filters.append(or_(Person.name.ilike(like, escape="\\"), Person.email.ilike(like, escape="\\")))

    total = db.scalar(select(func.count()).select_from(Person).where(*filters)) or 0
    # id breaks ties between equal names, so consecutive pages never repeat or skip a person.
    page = select(Person).where(*filters).order_by(Person.name, Person.id).limit(limit).offset(offset)
    return list(db.scalars(page).unique()), total
