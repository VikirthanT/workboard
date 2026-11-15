"""The Home tab of the bot: the person's open tasks, drawn fresh each time they open it and after each move they make there.

A query on the database and one call to Slack. It never raises: a Slack problem must not break the press that triggered it.

shortcut: each person's Show and Stage choices are kept in this process's memory, so a move made on the tab does not reset
them. They are forgotten when the listener restarts (the tab then opens on All); upgrade by keeping them in the database.
"""
import logging
from datetime import date

from sqlalchemy import select

from core.config import get_settings
from database.config import SessionLocal
from models import Person, Task
from slack import blocks, client

logger = logging.getLogger(__name__)
KEEP = object()  # "leave that filter as it is", as opposed to None, which means All
_filters: dict[str, dict[str, str | None]] = {}


def publish(slack_user_id: str, *, stage: str | None | object = KEEP, status: str | None | object = KEEP) -> None:
    """Draw this person's Home tab. `stage` and `status` change that filter (None is All); left out, the person's last
    choice stays."""
    settings = get_settings()
    if not settings.slack_configured:
        return
    chosen = _filters.setdefault(slack_user_id, {"stage": None, "status": None})
    if stage is not KEEP:
        chosen["stage"] = stage
    if status is not KEEP:
        chosen["status"] = status
    try:
        with SessionLocal() as db:
            person = db.scalar(select(Person).where(Person.slack_user_id == slack_user_id, Person.active.is_(True)))
            if person is None:
                view = blocks.home_unknown_view()
            else:
                tasks = list(db.scalars(select(Task).where(Task.assignee_id == person.id, Task.status != "done")))
                view = blocks.home_view(person, tasks, date.today(), chosen["stage"], chosen["status"])
        client.publish_home(settings.slack_bot_token, slack_user_id, view)
    except Exception:  # noqa: BLE001
        logger.exception("Drawing the Home tab failed")
