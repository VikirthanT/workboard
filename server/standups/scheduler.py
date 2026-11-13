"""Reads the standups on a schedule, so suggestions are waiting for the manager without anyone pressing Sync.

The times come from the environment (STANDUP_SYNC_SCHEDULE), for example `mon 11:00, mon 15:00, tue 11:00`: a day (mon to
sun, `weekdays`, or `daily`; leave it out for every day) and a 24-hour time, local (India) time, separated by commas. Run it as
a long-lived process beside the API:

    make scheduler-dev        (or: python -m standups.scheduler from server/)

At each time it reads every team that has a standup channel (the same read as the Sync button: posts already read and
unchanged are skipped, so a run with nothing new costs no model calls) and proposes suggestions for the manager to review.
It never creates a task. A newer standup replaces the person's older pending suggestions, so the schedule should include
the time the new week's standups are posted. An empty schedule makes it idle; the production stack runs it as the
`scheduler` service (docker-compose.yml).

shortcut: one process, runs the teams one after another; a long model call delays the next team, not the schedule. A press of Sync
at the very moment a scheduled run reaches the same post can collide on the unique rule; the loser fails and the next run
picks it up. Upgrade to a proper job queue if either becomes a problem.
"""
import logging
import threading
import time as clock
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from core.config import get_settings
from database.config import SessionLocal
from models import Team
from standups.services import sync

logger = logging.getLogger(__name__)

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
WEEKDAYS = frozenset(range(5))
# (the weekdays it applies to, or None for every day; the time of day)
Slot = tuple[frozenset[int] | None, time]


def parse_schedule(text: str) -> list[Slot]:
    """Turn "mon 11:00, weekdays 15:30, 09:00" into slots. Raises ValueError, naming the part, for anything it cannot read."""
    slots: list[Slot] = []
    for part in (p.strip().lower() for p in text.split(",")):
        if not part:
            continue
        day_text, _, clock_text = part.rpartition(" ")
        days: frozenset[int] | None
        if day_text.strip() in ("", "daily"):
            days = None
        elif day_text.strip() == "weekdays":
            days = WEEKDAYS
        elif day_text.strip()[:3] in DAYS and len(day_text.strip()) <= 9:
            days = frozenset({DAYS[day_text.strip()[:3]]})
        else:
            raise ValueError(f"Cannot read the day in “{part}”: use mon to sun, weekdays or daily.")
        try:
            hour, minute = (int(piece) for piece in clock_text.split(":"))
            slots.append((days, time(hour, minute)))
        except ValueError:
            raise ValueError(f"Cannot read the time in “{part}”: use 24-hour HH:MM, for example 11:30.") from None
    return slots


def next_run(now: datetime, slots: list[Slot]) -> datetime | None:
    """The first scheduled moment after `now`, or None when there are no slots."""
    upcoming = [
        moment
        for offset in range(8)
        for day in [(now + timedelta(days=offset)).date()]
        for days, at in slots
        if (days is None or day.weekday() in days) and (moment := datetime.combine(day, at)) > now
    ]
    return min(upcoming, default=None)


def sync_all_teams() -> None:
    """One scheduled run: every team with a standup channel, one at a time. A team that fails (the model is down, the
    standup database is unreachable) is logged and the next team still runs."""
    with SessionLocal() as db:
        team_ids = list(db.scalars(select(Team.id).where(Team.standup_channel_id.is_not(None)).order_by(Team.name)))
    for team_id in team_ids:
        try:
            with SessionLocal() as db:
                sync.sync_team_scheduled(db, team_id)
            logger.info("Standup sync done for team %s", team_id)
        except Exception:  # noqa: BLE001 - one team's problem must not stop the others or the schedule
            logger.exception("Standup sync failed for team %s", team_id)


def main(wait_if_empty: bool = False) -> None:
    schedule = get_settings().standup_sync_schedule
    try:
        slots = parse_schedule(schedule)
    except ValueError as err:
        print(f"Standup scheduler not started: STANDUP_SYNC_SCHEDULE is wrong. {err}")
        slots = []
    if not slots:
        print("Standup scheduler idle: set STANDUP_SYNC_SCHEDULE in .env, for example \"mon 11:00, tue 11:00\" (see .env.example).")
        if wait_if_empty:
            threading.Event().wait()
        return
    print(f"Standup scheduler running: {schedule}")
    while True:
        due = next_run(datetime.now(), slots)
        print(f"Next standup sync: {due:%a %d %b %H:%M}")
        while datetime.now() < due:
            clock.sleep(min(30.0, max(1.0, (due - datetime.now()).total_seconds())))  # short sleeps, so a changed clock is noticed
        sync_all_teams()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(wait_if_empty=True)
