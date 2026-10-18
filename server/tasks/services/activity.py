"""Write one entry to a task's timeline. Adds the row only; the calling command commits once."""
import uuid

from sqlalchemy.orm import Session

from models import Person, Task, TaskActivity


def record(
    db: Session,
    actor: Person,
    task: Task,
    kind: str,
    *,
    entry_id: uuid.UUID | None = None,
    field: str | None = None,
    old: str | None = None,
    new: str | None = None,
    note: str | None = None,
) -> None:
    db.add(
        TaskActivity(
            id=entry_id or uuid.uuid4(),
            task_id=task.id,
            actor_id=actor.id,
            kind=kind,
            field=field,
            old_value=old,
            new_value=new,
            note=note,
        )
    )
