"""Who is in a team's Slack channel, matched to the directory, for the "Pull from Slack" review. A query: it reads Slack and
the database and changes nothing (adding the ticked people is `members.add_members`).

Who may ask: an admin on any team, a manager on their own team (the same rule as adding a member). The channel is the
team's standup channel; Slack is asked with the bot token, and a private channel only answers if the bot was invited to it.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import AppError
from identity.services.lookup import get_team
from models import ROLE_MANAGER, Person, Team
from security.authorization import require_team_access
from slack import client as slack
from slack.errors import channel_error

AVAILABLE, ON_THIS_TEAM, ON_OTHER_TEAM, UNAVAILABLE = "available", "on_this_team", "on_other_team", "unavailable"


@dataclass
class Candidate:
    person: Person
    state: str
    team_name: str | None = None


@dataclass
class ChannelMembers:
    channel_id: str
    candidates: list[Candidate]
    not_in_directory: int


def list_channel_members(db: Session, actor: Person, team_id: uuid.UUID) -> ChannelMembers:
    team = get_team(db, team_id)
    require_team_access(actor, team)
    channel = team.standup_channel_id
    if not channel:
        raise AppError("standup_channel_not_set", "This team has no standup channel yet. Set one first, then pull its members.", 409)
    settings = get_settings()
    if not settings.slack_configured:
        raise AppError("slack_not_configured", "Slack is not set up on this server, so the channel cannot be read.", 501)
    slack_ids = _channel_ids(settings.slack_bot_token, channel)

    people = list(db.scalars(select(Person).where(Person.slack_user_id.in_(slack_ids)).order_by(Person.name)))
    team_names = dict(db.execute(select(Team.id, Team.name).where(Team.id.in_({p.team_id for p in people if p.team_id}))).all())
    return ChannelMembers(channel, [_candidate(p, team, team_names) for p in people], len(set(slack_ids)) - len(people))


def _channel_ids(token: str, channel: str) -> list[str]:
    try:
        return slack.channel_member_ids(token, channel)
    except slack.SlackError as err:
        raise channel_error(err) from err


def _candidate(person: Person, team: Team, team_names: dict[uuid.UUID, str]) -> Candidate:
    if person.team_id == team.id:
        return Candidate(person, ON_THIS_TEAM)
    if person.team_id is not None:
        return Candidate(person, ON_OTHER_TEAM, team_names.get(person.team_id))
    if not person.active or person.role == ROLE_MANAGER:
        return Candidate(person, UNAVAILABLE)
    return Candidate(person, AVAILABLE)
