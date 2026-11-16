"""What the Suggestions page shows for a team: each person, the standup they posted, and the suggestions from it.

Queries: they read and change nothing. Suggestions past their keep time are left out even before the next sync removes
them. The standup text is read live from the standup app's database; if that is unreachable the page still shows the
suggestions we hold, with no standup above them.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.exceptions import AppError
from identity.services.lookup import get_team
from models import ROLE_MANAGER, Person, Team, TaskSuggestion
from security.authorization import require_view_team
from standups.services.matching import person_matcher
from standups.standup_db import reader
from standups.states import KEEP_DAYS, week_start


@dataclass
class PersonSuggestions:
    person: Person
    standup: reader.Submission | None
    suggestions: list[TaskSuggestion] = field(default_factory=list)


@dataclass
class TeamPage:
    people: list[PersonSuggestions]
    # Why the standup posts could not be shown: "not_configured" (no STANDUP_DB_URL), "unreadable" (the database could
    # not be opened) or "channel_empty" (it was read, and holds no posts at all for this team's channel in the window,
    # which usually means the channel id is not the one the standup app uses). None when posts were found.
    # The suggestions are shown either way.
    standup_problem: str | None = None


def list_for_team(db: Session, actor: Person, team_id: uuid.UUID) -> TeamPage:
    """One entry per person on the team, manager first. `standup` is that person's latest submission in the team's
    channel from this week (an earlier week's standup is not shown), or None when they posted nothing this week (or the posts could not be read, see
    `standup_problem`). The standup blocks come straight from the standup database, so they do not depend on the
    language model: a failed or unset-up sync still leaves them."""
    team = get_team(db, team_id)
    require_view_team(actor, team)
    members = list(db.scalars(
        select(Person).where(Person.team_id == team.id).order_by((Person.role == ROLE_MANAGER).desc(), Person.name)
    ))
    entries = {p.id: PersonSuggestions(p, None) for p in members}
    match = person_matcher(members)

    submissions, problem = _recent_submissions(team.standup_channel_id)
    for sub in submissions:
        person = match(sub)
        if person is not None:
            entries[person.id].standup = sub  # oldest first, so the last one wins

    # Pending, rejected and approved ones all show for KEEP_DAYS after they last changed; after that they are history.
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    shown = db.scalars(
        select(TaskSuggestion)
        .where(TaskSuggestion.team_id == team.id, TaskSuggestion.state_at >= cutoff)
        .order_by(TaskSuggestion.created_at, TaskSuggestion.title)
    )
    for suggestion in shown:
        if suggestion.person_id in entries:
            entries[suggestion.person_id].suggestions.append(suggestion)
    return TeamPage(list(entries.values()), problem)


def get_suggestion(db: Session, actor: Person, suggestion_id: uuid.UUID) -> TaskSuggestion:
    suggestion = db.get(TaskSuggestion, suggestion_id)
    if suggestion is None:
        raise AppError("suggestion_not_found", "That suggestion no longer exists.", 404)
    require_view_team(actor, get_team(db, suggestion.team_id))
    return suggestion


def last_synced(db: Session, team_id: uuid.UUID) -> datetime | None:
    """When the whole team's standups were last read, whether or not a post was found, or None if they never were."""
    return db.scalar(select(Team.standup_synced_at).where(Team.id == team_id))


def _recent_submissions(channel_id: str | None) -> tuple[list[reader.Submission], str | None]:
    """The recent posts and why they could not be read (None when they could). Never raises: a standup database that
    is missing, locked or unset must not take the whole page down."""
    if not channel_id:
        return [], None
    try:
        submissions = reader.list_submissions(channel_id, week_start(date.today()))  # this week's standups only
        # Nothing at all in this channel: usually the team's channel is not the one the standup app uses.
        return submissions, (None if submissions else "channel_empty")
    except AppError as err:
        if err.code == "standups_not_configured":
            return [], "not_configured"
        raise
    except SQLAlchemyError:
        return [], "unreadable"
