"""The standup database reader: reads one channel's submissions, and can never write to the file."""
import sqlite3
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from core.config import settings
from core.exceptions import AppError
from standups.standup_db import reader

SCHEMA = """
CREATE TABLE channels (id INTEGER PRIMARY KEY, slack_channel_id TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE persons (id INTEGER PRIMARY KEY, display_name TEXT NOT NULL, slack_user_id TEXT, email TEXT);
CREATE TABLE standups (id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, standup_date DATE NOT NULL);
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY, standup_id INTEGER NOT NULL, person_id INTEGER NOT NULL, last_week TEXT, this_week TEXT,
    blockers TEXT, combined TEXT, raw_content TEXT NOT NULL, is_late_reply BOOLEAN, source TEXT, created_at TEXT
);
"""


@pytest.fixture
def standup_db(tmp_path, monkeypatch):
    path = tmp_path / "standup.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executescript(
        """
        INSERT INTO channels VALUES (1, 'C_NPI', 'standup-npi'), (2, 'C_OTHER', 'standup-other');
        INSERT INTO persons VALUES (1, 'Asha', 'U_ASHA', 'asha@example.org'), (2, 'Ravi', NULL, NULL);
        INSERT INTO standups VALUES (1, 1, '2026-10-05'), (2, 1, '2026-10-12'), (3, 2, '2026-10-12');
        INSERT INTO submissions VALUES
            (10, 1, 1, 'old work', 'old plan', '', NULL, 'raw old', 0, 'bot', '2026-10-05 04:00:00'),
            (11, 2, 1, NULL, 'build the jig', 'waiting on parts', NULL, 'raw new', 1, 'slackbot_modal', '2026-10-14 04:09:21'),
            (12, 2, 2, NULL, NULL, NULL, 'combined text', 'raw ravi', 0, 'thread_reply', 'not a time'),
            (13, 3, 1, NULL, 'other channel plan', NULL, NULL, 'raw other', 0, 'bot', '2026-10-12 04:00:00');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(settings, "standup_db_url", f"sqlite:///{path}")
    reader._engine.cache_clear()
    yield path
    reader._engine.cache_clear()


def test_it_reads_one_channels_submissions_since_a_date_oldest_first(standup_db):
    rows = reader.list_submissions("C_NPI", date(2026, 10, 12))

    assert [r.id for r in rows] == [11, 12]  # not 10 (older), not 13 (another channel)
    asha, ravi = rows
    assert (asha.person_name, asha.email, asha.slack_user_id) == ("Asha", "asha@example.org", "U_ASHA")
    assert asha.standup_date == date(2026, 10, 12)
    assert asha.this_week == "build the jig" and asha.blockers == "waiting on parts"
    assert asha.is_late_reply is True and asha.source == "slackbot_modal"
    assert asha.posted_at == datetime(2026, 10, 14, 4, 9, 21, tzinfo=timezone.utc)  # when they posted, in UTC, not the standup date
    assert rows[1].posted_at is None  # an unreadable time is None, not an error
    assert ravi.email is None and ravi.slack_user_id is None
    assert ravi.this_week is None and ravi.combined == "combined text" and ravi.is_late_reply is False


def test_it_lists_the_channels_by_name(standup_db):
    assert [(c.slack_channel_id, c.name) for c in reader.list_channels()] == [
        ("C_NPI", "standup-npi"),
        ("C_OTHER", "standup-other"),
    ]


def test_the_connection_is_read_only(standup_db):
    with reader._engine().connect() as conn:
        with pytest.raises(OperationalError):
            conn.execute(text("DELETE FROM submissions"))


def test_a_sqlite_url_is_opened_read_only_and_other_urls_are_left_alone():
    assert reader.read_only_url("sqlite:////opt/standup-bot/standup.db") == (
        "sqlite:///file:/opt/standup-bot/standup.db?mode=ro&uri=true"
    )
    assert reader.read_only_url("postgresql://reader@host/standup") == "postgresql://reader@host/standup"


def test_without_a_url_it_says_the_standup_database_is_not_set_up(monkeypatch):
    monkeypatch.setattr(settings, "standup_db_url", "")
    reader._engine.cache_clear()

    with pytest.raises(AppError) as err:
        reader.list_channels()

    assert err.value.status_code == 501
