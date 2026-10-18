"""Queries shared by the command services: fetch one team or person, or fail with a 404."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from models import Person, Team


def get_team(db: Session, team_id: uuid.UUID, *, lock: bool = False) -> Team:
    """lock=True takes a row lock (FOR UPDATE) so two admins editing one team cannot interleave."""
    query = select(Team).where(Team.id == team_id)
    if lock:
        # `of=Team`: Postgres refuses to lock the nullable side of the joined manager row.
        query = query.with_for_update(of=Team)
    team = db.scalar(query)
    if team is None:
        raise AppError("team_not_found", "That team does not exist.", 404)
    return team


def get_person(db: Session, person_id: uuid.UUID, *, lock: bool = False) -> Person:
    query = select(Person).where(Person.id == person_id)
    if lock:
        query = query.with_for_update(of=Person)
    person = db.scalar(query)
    if person is None:
        raise AppError("person_not_found", "That person is not in the directory.", 404)
    return person
