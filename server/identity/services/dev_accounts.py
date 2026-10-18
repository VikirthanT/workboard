"""The dev sign-in list: who the login page offers while the server runs with DEV_AUTH (local development only).
A query: it reads and changes nothing. The route that serves it answers 404 unless DEV_AUTH is on.
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import ROLE_MANAGER, Person
from security.authorization import can_login

# A couple of plain team members are listed too, so the refusal ("only managers and admins can sign in") can be shown.
REFUSED_EXAMPLES = 2


def list_dev_accounts(db: Session) -> list[tuple[Person, bool]]:
    """Every active admin and manager (they can sign in), then a few plain members (they cannot). With the flag."""
    signers = db.scalars(
        select(Person).where(Person.active, or_(Person.is_admin, Person.role == ROLE_MANAGER)).order_by(Person.name)
    ).unique()
    refused = db.scalars(
        select(Person)
        .where(Person.active, Person.is_admin.is_(False), Person.role != ROLE_MANAGER, Person.team_id.is_not(None))
        .order_by(Person.name)
        .limit(REFUSED_EXAMPLES)
    ).unique()
    return [(person, can_login(person)) for person in [*signers, *refused]]
