"""Which standup channels exist, for the admin's channel picker. A query: it reads and changes nothing."""
from models import Person
from security.authorization import require_admin
from standups.standup_db import reader


def list_channels(actor: Person) -> list[reader.Channel]:
    require_admin(actor)
    return reader.list_channels()
