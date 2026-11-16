"""Queue a new task for its Slack announcement. Called by the task commands before they commit, so the row and the task
land together or not at all. A no-op when Slack is not set up, so nothing piles up while it is off."""
import uuid

from sqlalchemy.orm import Session

from core.config import get_settings
from models import SlackOutbox


def record_task_added(db: Session, team_id: uuid.UUID, task_id: uuid.UUID) -> None:
    if get_settings().slack_configured:
        db.add(SlackOutbox(team_id=team_id, task_id=task_id))
