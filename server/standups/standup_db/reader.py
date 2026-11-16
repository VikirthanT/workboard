"""Read-only access to the standup app's database (its tables: channels, persons, standups, submissions).

We never write to it. A SQLite URL is opened with mode=ro, so even a bug here cannot change the file; any other
database is used as given (ask its owner for a read-only login). The standup app's schema is theirs: confirm a
column with them before relying on a new one.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from core.config import get_settings
from core.exceptions import AppError


@dataclass(frozen=True)
class Channel:
    slack_channel_id: str
    name: str


@dataclass(frozen=True)
class Submission:
    id: int
    standup_date: date
    person_name: str
    email: str | None
    slack_user_id: str | None
    last_week: str | None
    this_week: str | None
    blockers: str | None
    combined: str | None
    raw_content: str
    is_late_reply: bool
    source: str | None
    # When the person actually posted (the standup app's `created_at`, which it stores in UTC), not the standup's date.
    posted_at: datetime | None = None


def read_only_url(url: str) -> str:
    """sqlite:////abs/path becomes sqlite:///file:/abs/path?mode=ro&uri=true; any other URL is returned unchanged."""
    if url.startswith("sqlite:///") and "mode=ro" not in url:
        return f"sqlite:///file:{url[len('sqlite:///'):]}?mode=ro&uri=true"
    return url


@lru_cache
def _engine() -> Engine:
    url = get_settings().standup_db_url
    if not url:
        raise AppError("standups_not_configured", "The standup database is not set up on this server.", 501)
    # NullPool: every read opens the file afresh. The standup app owns it and it can be replaced under us (a restore, or
    # the demo file being rewritten), and a pooled connection would keep reading the old, deleted copy.
    return create_engine(read_only_url(url), poolclass=NullPool)


def list_channels() -> list[Channel]:
    with _engine().connect() as conn:
        rows = conn.execute(text("SELECT slack_channel_id, name FROM channels ORDER BY name"))
        return [Channel(r.slack_channel_id, r.name) for r in rows]


def list_submissions(channel_id: str, since: date) -> list[Submission]:
    """Every submission posted in one standup channel on or after `since`, oldest first."""
    query = text(
        """
        SELECT s.id, st.standup_date, p.display_name, p.email, p.slack_user_id,
               s.last_week, s.this_week, s.blockers, s.combined, s.raw_content, s.is_late_reply, s.source, s.created_at
        FROM submissions s
        JOIN standups st ON st.id = s.standup_id
        JOIN channels c ON c.id = st.channel_id
        JOIN persons p ON p.id = s.person_id
        WHERE c.slack_channel_id = :channel AND st.standup_date >= :since
        ORDER BY st.standup_date, s.id
        """
    )
    with _engine().connect() as conn:
        rows = conn.execute(query, {"channel": channel_id, "since": since.isoformat()})
        return [
            Submission(
                id=r.id,
                # SQLite hands dates back as text, other databases as dates: str() then parse works for both.
                standup_date=date.fromisoformat(str(r.standup_date)),
                person_name=r.display_name,
                email=r.email,
                slack_user_id=r.slack_user_id,
                last_week=r.last_week,
                this_week=r.this_week,
                blockers=r.blockers,
                combined=r.combined,
                raw_content=r.raw_content,
                is_late_reply=bool(r.is_late_reply),
                source=r.source,
                posted_at=_moment(r.created_at),
            )
            for r in rows
        ]


def _moment(value) -> datetime | None:
    """The standup app stores UTC without a zone ('2026-10-12 04:09:21'); the zone is attached here. Anything unreadable is None."""
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
