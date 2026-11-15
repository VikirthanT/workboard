"""The schedule format shared by the standup scheduler and the directory sync."""
from datetime import datetime, time

import pytest

from core.schedule import next_run, parse_schedule


def test_a_day_and_a_24_hour_time_make_a_slot():
    assert parse_schedule("tue 12:00, wed 12:00") == [(frozenset({1}), time(12, 0)), (frozenset({2}), time(12, 0))]
    assert parse_schedule("sun 22:00") == [(frozenset({6}), time(22, 0))]


def test_weekdays_daily_and_a_bare_time_are_understood_and_blanks_are_ignored():
    assert parse_schedule("weekdays 15:30") == [(frozenset(range(5)), time(15, 30))]
    assert parse_schedule("daily 09:00, 18:45, ") == [(None, time(9, 0)), (None, time(18, 45))]
    assert parse_schedule("") == []


@pytest.mark.parametrize("text, message", [("funday 11:00", "day"), ("tue 25:99", "time"), ("tue noon", "time")])
def test_what_it_cannot_read_is_named(text, message):
    with pytest.raises(ValueError) as err:
        parse_schedule(text)
    assert message in str(err.value) and text.split(",")[0] in str(err.value)


def test_the_next_run_is_the_first_moment_after_now():
    slots = parse_schedule("tue 12:00, wed 12:00")
    monday = datetime(2026, 11, 16, 9, 0)

    assert next_run(monday, slots) == datetime(2026, 11, 17, 12, 0)
    assert next_run(datetime(2026, 11, 17, 12, 0), slots) == datetime(2026, 11, 18, 12, 0)  # a run at this very moment has gone
    assert next_run(datetime(2026, 11, 18, 12, 1), slots) == datetime(2026, 11, 24, 12, 0)  # next week


def test_sunday_night_runs_once_a_week_and_no_slots_means_never():
    assert next_run(datetime(2026, 11, 15, 23, 0), parse_schedule("sun 22:00")) == datetime(2026, 11, 22, 22, 0)
    assert next_run(datetime(2026, 11, 15, 21, 0), parse_schedule("sun 22:00")) == datetime(2026, 11, 15, 22, 0)
    assert next_run(datetime(2026, 11, 15, 21, 0), []) is None
