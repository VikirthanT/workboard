"""Write a task's `task.delete` audit entry, with a snapshot of the task and its timeline. Adds the row only; the
calling command commits. Used when one task is deleted and when a whole team (and so all its tasks) is deleted."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from identity import states as identity_states
from identity.services import audit
from models import Person, Task, TaskActivity


def record_task_deleted(db: Session, actor: Person, task: Task, reason: str | None = None) -> None:
    history = db.scalars(select(TaskActivity).where(TaskActivity.task_id == task.id).order_by(TaskActivity.created_at, TaskActivity.id))
    assignee = db.get(Person, task.assignee_id) if task.assignee_id else None
    audit.record(
        db, actor, identity_states.TASK_DELETE, team_id=task.team_id, person_id=task.assignee_id, reason=reason,
        details={
            "task_id": str(task.id),
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "assignee": assignee.name if assignee else None,
            "created_at": task.created_at.isoformat(),
            "timeline": [
                {"kind": a.kind, "field": a.field, "old": a.old_value, "new": a.new_value, "note": a.note, "at": a.created_at.isoformat()}
                for a in history
            ],
        },
    )
