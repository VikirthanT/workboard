"""Task endpoints: create, read, edit, move between columns, comment, delete.

A router only reads the request, calls one service function, and shapes the reply. The rules (who may act, which
moves are allowed, what needs a reason) live in `tasks/services/commands.py` and `security/authorization.py`.
Each handler that changes something runs one command, then one query to build the response, so the reply always
carries the task as the caller may now see it, including the `actions` they are allowed to take next.

Every endpoint needs a signed-in person (401 otherwise). Only the manager of the task's team may change it (403
`forbidden`); an admin may read any team's tasks but never change them unless they run that team. Errors come
back as {"detail": {"code", "message"}}; the codes are listed in `tasks/README.md`.
"""
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database.config import get_db
from models import Person
from security.authentication import get_current_person
from tasks import schemas
from tasks.services import commands, queries

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=schemas.TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(body: schemas.TaskCreate, db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """Create a task on the caller's own team. It starts in To Do.

    Who: the manager of a team (an admin on no team has nowhere to put it: 403 `forbidden`).
    Body: {title, assignee_id, description?, priority? (low | medium | high, default medium), due_at? (a date)}.
    There is no `team_id`: the task always lands on the caller's team. The assignee must be an active person on
    that team; the manager may assign to themselves. The title is trimmed and may not be blank or over 140 characters.
    Errors: 422 `invalid_assignee`, 422 `title_required`; 404 `person_not_found` for an unknown assignee id.
    """
    task_id = uuid.uuid4()
    commands.create_task(db, actor, task_id, body.title, body.description, body.priority, body.due_at, body.assignee_id)
    return queries.get_task(db, actor, task_id)


@router.get("/{task_id}", response_model=schemas.TaskDetail)
def task_detail(task_id: uuid.UUID, db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """One task with its full timeline (oldest first): creation, status moves, edits, reassignments, comments.

    Who: the manager of the task's team, or any admin (read-only). Anyone else gets 403 `forbidden`.
    Done tasks stay readable forever. Errors: 404 `task_not_found`.
    """
    return queries.get_task_detail(db, actor, task_id)


@router.patch("/{task_id}", response_model=schemas.TaskResponse)
def update_task(
    task_id: uuid.UUID,
    body: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Change a task's title, description, priority, due date or assignee.

    Who: the manager of the task's team.
    Body: send only what changes. A field you leave out stays as it is; `due_at: null` clears the date; a null
    title, priority, description or assignee is ignored. Status is not editable here: use `/status`.
    Each field that really changed becomes one entry on the timeline (a new assignee is a "reassign" entry).
    Errors: 409 `task_done` (a finished task cannot be reassigned, but can be edited), 422 `invalid_assignee`,
    422 `title_required`, 404 `task_not_found`.
    """
    commands.update_task(db, actor, task_id, body.model_dump(exclude_unset=True))
    return queries.get_task(db, actor, task_id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """Delete a task and its timeline for good.

    Who: the manager of the task's team.
    Only while the task is To Do or In Progress. Once it has been Blocked, in Review or Done it carries history
    worth keeping, so it cannot be deleted (409 `not_deletable`). Returns 204 with no body.
    """
    commands.delete_task(db, actor, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/status", response_model=schemas.TaskResponse)
def move_task(
    task_id: uuid.UUID,
    body: schemas.StatusMove,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Move a card to another column.

    Who: the manager of the task's team.
    Body: {to, note?}. `to` is one of todo, in_progress, blocked, review, done. Only the moves the board allows
    from the task's current status are accepted (each task lists them in `actions.transitions`).
    `note` is required when the move needs a reason: blocking, moving back to To Do, sending back from Review,
    reopening a Done task, and (as "remarks") every move into Done. It is stored on the timeline entry.
    `completed_on` (only with `to: done`) is the day the work really finished: from the due date (when it has passed) up to today.
    Errors: 409 `invalid_transition`, 422 `reason_required`, 422 `completed_on_invalid`, 422 `completed_on_not_done`, 404 `task_not_found`.
    """
    commands.move_task(db, actor, task_id, body.to, body.note, body.completed_on)
    return queries.get_task(db, actor, task_id)


@router.post("/{task_id}/comments", response_model=schemas.ActivityResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: uuid.UUID,
    body: schemas.CommentCreate,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Add a comment to a task. It appears on the task's timeline with the author and the time.

    Who: the manager of the task's team.
    Body: {body} (1 to 1000 characters, trimmed). Not allowed on a Done task: reopen it first (409 `task_done`).
    Returns the new timeline entry. Comments cannot be edited or deleted afterwards.
    """
    entry_id = uuid.uuid4()
    commands.add_comment(db, actor, task_id, entry_id, body.body)
    return queries.get_activity(db, actor, entry_id)
