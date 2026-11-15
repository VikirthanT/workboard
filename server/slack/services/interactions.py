"""What happens when someone presses a button on their DM card. Each function takes who pressed (their Slack user id) and
returns a message to show them when something went wrong, or None. The rules are the server's own: the move goes through
`commands.move_task_as_assignee`, so what the card offers and what is allowed can never drift apart.
"""
import logging
import uuid

from sqlalchemy import select

from core.exceptions import AppError
from database.config import SessionLocal
from models import Person, Task, TaskActivity, Team
from security.authorization import assignee_transitions_for, can_assignee_comment
from slack import blocks
from slack.services import dm, home
from tasks.services import commands

logger = logging.getLogger(__name__)
NOT_FOUND = "I could not find you in the Work Board directory, so I cannot move this task."


def _person(db, slack_user_id: str) -> Person | None:
    return db.scalar(select(Person).where(Person.slack_user_id == slack_user_id, Person.active.is_(True)))


def move(slack_user_id: str, task_id: str, to: str, reason: str | None) -> str | None:
    """Move the task as the person who pressed. The move is on the timeline under their name, marked as from Slack.
    Redraws the card afterwards."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        return "That task could not be found."
    with SessionLocal() as db:
        person = _person(db, slack_user_id)
        if person is None:
            return NOT_FOUND
        try:
            commands.move_task_as_assignee(db, person, task_uuid, to, reason, source="slack")
        except AppError as err:
            db.rollback()
            dm.refresh_card(task_uuid)  # the dropdown showed the choice before it was refused: put it back
            home.publish(slack_user_id)
            return err.message
        person_id = person.id
    dm.refresh_card(task_uuid)
    dm.post_move(task_uuid, person_id, to, reason)  # their own reason (Blocked, or back to To Do), kept in the thread
    home.publish(slack_user_id)  # and the Home tab, if the move was made there
    return None


def reset_card(task_id: str, slack_user_id: str | None = None) -> None:
    """Redraw a task's card (and the person's Home tab) from its real state, for when a dropdown shows a choice that was not
    carried out."""
    try:
        dm.refresh_card(uuid.UUID(task_id))
    except ValueError:
        pass
    if slack_user_id:
        home.publish(slack_user_id)


def comment(slack_user_id: str, task_id: str, text: str) -> str | None:
    """Save the comment on the task as the person who pressed (on the timeline under their name, marked as from Slack) and
    post it in the card's thread."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        return "That task could not be found."
    with SessionLocal() as db:
        person = _person(db, slack_user_id)
        if person is None:
            return NOT_FOUND
        try:
            commands.add_comment_as_assignee(db, person, task_uuid, uuid.uuid4(), text, source="slack")
        except AppError as err:
            db.rollback()
            return err.message
        name, said = person.name, text.strip()
    dm.post_comment(task_uuid, name, "you", said)
    return None


def comment_view(slack_user_id: str, task_id: str) -> tuple[dict | None, str | None]:
    """The comment form to open: (view, None), or (None, why it cannot be opened)."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        return None, "That task could not be found."
    with SessionLocal() as db:
        person = _person(db, slack_user_id)
        task = db.get(Task, task_uuid)
        if person is None or task is None:
            return None, NOT_FOUND if person is None else "That task could not be found."
        if not can_assignee_comment(person, task):
            return None, "You cannot comment on this task any more."
        return blocks.comment_modal(task), None


def details_view(slack_user_id: str, task_id: str) -> tuple[dict | None, str | None]:
    """The Details popup of a task on the Home tab: (view, None), or (None, why it cannot be opened). Only the task's own
    assignee sees it: the thread holds the manager's reasons and comments."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        return None, "That task could not be found."
    with SessionLocal() as db:
        person = _person(db, slack_user_id)
        task = db.get(Task, task_uuid)
        if person is None:
            return None, NOT_FOUND
        if task is None or task.assignee_id != person.id:
            return None, "That task could not be found."
        entries = list(db.scalars(
            select(TaskActivity).where(TaskActivity.task_id == task.id).order_by(TaskActivity.created_at.desc()).limit(blocks.THREAD_MAX_ENTRIES)
        ))[::-1]  # the newest few, shown oldest first
        names = {p.id: p.name for p in db.scalars(select(Person).where(Person.id.in_({e.actor_id for e in entries if e.actor_id})))}
        manager_id = team.manager_id if (team := db.get(Team, task.team_id)) else None

        def role(actor_id) -> str:  # the same three roles the DM thread labels
            if actor_id is None:
                return ""
            return "you" if actor_id == task.assignee_id else "manager" if actor_id == manager_id else "admin"

        thread = [
            (names.get(e.actor_id, "Someone"), role(e.actor_id), e.kind, e.field, e.old_value, e.new_value, e.note, e.source, e.created_at)
            for e in entries
        ]
        return blocks.task_detail_modal(task, thread, can_assignee_comment(person, task)), None


def reason_view(slack_user_id: str, task_id: str, to: str) -> tuple[dict | None, str | None]:
    """The reason form to open for a move that needs one: (view, None), or (None, why it cannot be opened)."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        return None, "That task could not be found."
    with SessionLocal() as db:
        person = _person(db, slack_user_id)
        task = db.get(Task, task_uuid)
        if person is None or task is None:
            return None, NOT_FOUND if person is None else "That task could not be found."
        if not any(m.to == to for m in assignee_transitions_for(person, task)):
            return None, f"You cannot move this task to {to.replace('_', ' ')} from here."
        return blocks.reason_modal(task, to), None
