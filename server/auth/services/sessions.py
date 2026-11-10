"""Ending sessions (a command: writes, commits once, returns nothing)."""
from sqlalchemy import update
from sqlalchemy.orm import Session

from models import Person


def end_sessions(db: Session, person: Person) -> None:
    """Sign the person out everywhere: their session tokens carry the old `session_version`, so none works any more.
    One UPDATE adds one in the database, so two sign-outs at once both count."""
    db.execute(update(Person).where(Person.id == person.id).values(session_version=Person.session_version + 1))
    db.commit()
