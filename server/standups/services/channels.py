"""Which standup channels exist, for the channel picker of an admin or a manager. A query: it reads and changes nothing."""
from core.exceptions import AppError
from models import ROLE_MANAGER, Person
from security.authorization import is_admin
from standups.standup_db import reader


def list_channels(actor: Person) -> list[reader.Channel]:
    if not (is_admin(actor) or actor.role == ROLE_MANAGER):
        raise AppError("forbidden", "Only an admin or a manager can do this.", 403)
    return reader.list_channels()
