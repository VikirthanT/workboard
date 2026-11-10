"""Fetch one task (and its team) for a command service, or fail with a 404."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity.services.lookup import get_team
from models import Person, Task, Team
from security import authorization


def get_task(db: Session, task_id: uuid.UUID, *, lock: bool = False) -> Task:
    """lock=True takes a row lock so two moves of one card cannot interleave."""
    query = select(Task).where(Task.id == task_id)
    if lock:
        query = query.with_for_update()
    task = db.scalar(query)
    if task is None:
        raise AppError("task_not_found", "That task does not exist.", 404)
    return task


def own_team(db: Session, actor: Person) -> Team:
    """The actor's own team, for a command that adds tasks to it; anyone who could not act on it is refused."""
    if actor.team_id is None:
        raise AppError("forbidden", "You are not on a team.", 403)
    team = get_team(db, actor.team_id)
    authorization.require_act(actor, team)
    return team


def get_task_and_team(db: Session, task_id: uuid.UUID, *, lock: bool = False) -> tuple[Task, Team]:
    task = get_task(db, task_id, lock=lock)
    return task, get_team(db, task.team_id)
