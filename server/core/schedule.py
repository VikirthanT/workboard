"""Weekly and daily run times for the background services (the standup scheduler, the Slack directory sync).

A schedule is written in the environment as a comma-separated list such as `mon 11:00, weekdays 15:30, 09:00`: a day (mon to
sun, `weekdays` or `daily`; left out means every day) and a 24-hour time, in India time (the server's clock, TZ=Asia/Kolkata).
"""
from datetime import datetime, time, timedelta

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
