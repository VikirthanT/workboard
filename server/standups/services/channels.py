"""Standup channels, for an admin or a manager. Queries: they read and change nothing."""
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.exceptions import AppError
from models import ROLE_MANAGER, Person
from security.authorization import is_admin
from slack import client as slack
from slack.errors import channel_error
from standups.standup_db import reader


def _require_admin_or_manager(actor: Person) -> None:
    if not (is_admin(actor) or actor.role == ROLE_MANAGER):
        raise AppError("forbidden", "Only an admin or a manager can do this.", 403)


def list_channels(actor: Person) -> list[reader.Channel]:
    """The channels in the standup app's own database."""
    _require_admin_or_manager(actor)
    return reader.list_channels()


def channel_name(actor: Person, channel_id: str) -> str:
    """The name of this channel id, so the team page can show #name beside the id that was typed. The standup app's own
    channel list answers first (no Slack call, and its names are the ones the standups use); a channel it does not list is
    asked of Slack. The error says when neither knows it, or when the bot has not been invited to a private channel."""
    _require_admin_or_manager(actor)
    channel_id = channel_id.strip()
    listed = _standup_app_channels()
    if listed is not None and channel_id in listed:
        return listed[channel_id]
    settings = get_settings()
    if not settings.slack_configured:
        if listed is not None:
            raise AppError("channel_not_found", "The standup app does not know this channel id. Check it.", 404)
        raise AppError("slack_not_configured", "Neither the standup database nor Slack is set up here, so the channel name cannot be looked up.", 501)
    try:
        return slack.channel_name(settings.slack_bot_token, channel_id)
    except slack.SlackError as err:
        raise channel_error(err) from err


def _standup_app_channels() -> dict[str, str] | None:
    """Slack channel id -> name from the standup app's database, or None when that database is not set up or cannot be read."""
    try:
        return {c.slack_channel_id: c.name for c in reader.list_channels()}
    except (AppError, SQLAlchemyError):
        return None
