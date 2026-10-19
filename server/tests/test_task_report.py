"""The team report: the numbers (tasks/services/report.py) and the endpoint."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from models import Person, Task
from tasks.services.report import report_counts
from tests.conftest import make_team

TODAY = date(2026, 10, 17)


def at(day: date) -> datetime:
    """Midday UTC on a day, so the server's own time zone cannot move it to another date."""
    return datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)


def task(**fields) -> Task:
    defaults = {"team_id": uuid.uuid4(), "title": "t", "status": "todo", "returned_count": 0, "created_at": at(TODAY)}
    return Task(**{**defaults, **fields})


def finished(created: date, closed: date, due: date | None = None, **fields) -> Task:
    return task(status="done", created_at=at(created), closed_at=at(closed), due_at=due, **fields)


# ---- the numbers ----

def test_open_counts_are_the_current_state_whatever_the_period():
    tasks = [task(status="todo"), task(status="in_progress"), task(status="blocked"), task(status="review"), finished(TODAY, TODAY)]
    nowhere = (date(2020, 1, 1), date(2020, 1, 2))

    for window in (None, nowhere):
        counts = report_counts(tasks, window, TODAY)
        assert (counts.todo, counts.in_progress, counts.blocked, counts.review) == (1, 1, 1, 1)


def test_assigned_done_and_returned_are_limited_to_the_period():
    week = (date(2026, 10, 12), date(2026, 10, 18))
    inside = finished(date(2026, 10, 13), date(2026, 10, 15), returned_count=2)
    created_before = finished(date(2026, 10, 1), date(2026, 10, 14), returned_count=5)
    after = task(created_at=at(date(2026, 10, 25)), returned_count=7)

    counts = report_counts([inside, created_before, after], week, TODAY)

    assert (counts.assigned, counts.done, counts.returned) == (1, 2, 2)  # only `inside` was created in the week


def test_completion_rate_is_done_over_assigned_and_none_when_nothing_was_assigned():
    tasks = [finished(TODAY, TODAY), task(), task(), task()]

    assert report_counts(tasks, None, TODAY).completion_rate == 0.25
    assert report_counts([], None, TODAY).completion_rate is None
    assert report_counts([task()], None, TODAY).done == 0


def test_on_time_counts_only_done_tasks_that_had_a_due_date():
    on_time = finished(TODAY, TODAY, due=TODAY)
    late = finished(TODAY, TODAY + timedelta(days=2), due=TODAY)
    no_date = finished(TODAY, TODAY)

    assert report_counts([on_time, late, no_date], None, TODAY).on_time_rate == 0.5
    assert report_counts([no_date], None, TODAY).on_time_rate is None


def test_average_days_to_close_and_overdue():
    quick = finished(date(2026, 10, 10), date(2026, 10, 12))
    slow = finished(date(2026, 10, 1), date(2026, 10, 7))
    late_open = task(due_at=date(2026, 10, 1))
    late_but_done = finished(date(2026, 9, 1), date(2026, 9, 30), due=date(2026, 9, 15))

    counts = report_counts([quick, slow, late_open, late_but_done], None, TODAY)

    assert counts.avg_days_to_close == (2 + 6 + 29) / 3
    assert counts.overdue == 1  # a Done task is never overdue
    assert report_counts([task()], None, TODAY).avg_days_to_close is None


# ---- the endpoint ----

def create(directory, npi, assignee, title):
    res = directory.call(npi["asha"], "POST", "/tasks", json={"title": title, "assignee_id": str(assignee.id)})
    assert res.status_code == 201, res.text
    return res.json()


def finish(directory, npi, task_json):
    for to, note in (("in_progress", None), ("done", "shipped")):
        res = directory.call(npi["asha"], "POST", f"/tasks/{task_json['id']}/status", json={"to": to, "note": note})
        assert res.status_code == 200, res.text


def report(directory, who, query):
    res = directory.call(who, "GET", f"/reports/team{query}")
    assert res.status_code == 200, res.text
    return res.json()


def test_the_report_gives_team_totals_and_one_row_per_person_sorted_by_name(directory, npi):
    finish(directory, npi, create(directory, npi, npi["ravi"], "A"))
    create(directory, npi, npi["ravi"], "B")
    create(directory, npi, npi["asha"], "C")
    today = date.today().isoformat()

    result = report(directory, npi["asha"], f"?from={today}&to={today}")

    totals = result["all_time"]["totals"]
    assert (totals["todo"], totals["done"], totals["assigned"], totals["completion_rate"]) == (2, 1, 3, 1 / 3)
    rows = {p["person"]["name"]: p["counts"] for p in result["all_time"]["people"]}
    assert list(rows) == ["Asha", "Ravi"]
    assert (rows["Ravi"]["todo"], rows["Ravi"]["done"], rows["Asha"]["todo"]) == (1, 1, 1)
    assert result["period"]["totals"]["assigned"] == 3


def test_a_period_with_no_new_work_keeps_the_open_counts_but_has_no_rates(directory, npi):
    create(directory, npi, npi["ravi"], "A")
    long_ago = "2020-01-01"

    result = report(directory, npi["asha"], f"?from={long_ago}&to={long_ago}")

    period = result["period"]["totals"]
    assert (period["todo"], period["assigned"], period["done"], period["completion_rate"]) == (1, 0, 0, None)
    assert result["all_time"]["totals"]["assigned"] == 1


def test_the_person_filter_narrows_the_report(directory, npi):
    create(directory, npi, npi["ravi"], "A")
    create(directory, npi, npi["asha"], "B")
    today = date.today().isoformat()

    result = report(directory, npi["asha"], f"?from={today}&to={today}&person={npi['ravi'].id}")

    assert result["all_time"]["totals"]["todo"] == 1
    assert [p["person"]["name"] for p in result["all_time"]["people"]] == ["Ravi"]


def test_a_backwards_or_malformed_range_is_refused(directory, npi):
    backwards = directory.call(npi["asha"], "GET", "/reports/team?from=2026-10-18&to=2026-10-12")
    junk = directory.call(npi["asha"], "GET", "/reports/team?from=yesterday&to=today")
    missing = directory.call(npi["asha"], "GET", "/reports/team")

    assert (backwards.status_code, backwards.json()["detail"]["code"]) == (422, "invalid_range")
    assert junk.status_code == 422 and missing.status_code == 422


def test_an_admin_reads_any_team_a_manager_only_their_own(directory, admin, npi):
    other = directory.person("Omar")
    qa = make_team(directory, admin, "QA", other)
    today = date.today().isoformat()
    query = f"?from={today}&to={today}&team={npi['team']['id']}"

    assert directory.call(admin, "GET", f"/reports/team{query}").status_code == 200
    peek = directory.call(other, "GET", f"/reports/team{query}")
    assert (peek.status_code, peek.json()["detail"]["code"]) == (403, "forbidden")
    assert directory.call(other, "GET", f"/reports/team?from={today}&to={today}&team={qa['id']}").status_code == 200
    assert directory.call(None, "GET", f"/reports/team{query}").status_code == 401


def test_an_admin_with_no_team_must_choose_one(directory, admin):
    assert directory.call(admin, "GET", "/reports/team?from=2026-10-12&to=2026-10-18").json()["detail"]["code"] == "choose_team"


# ---- edges ----

def test_a_team_with_no_tasks_reports_zeros_and_no_rates_not_errors(directory, npi):
    today = date.today().isoformat()

    result = report(directory, npi["asha"], f"?from={today}&to={today}")

    for block in (result["all_time"], result["period"]):
        totals = block["totals"]
        assert (totals["todo"], totals["done"], totals["assigned"], totals["overdue"]) == (0, 0, 0, 0)
        assert (totals["completion_rate"], totals["on_time_rate"], totals["avg_days_to_close"]) == (None, None, None)
        assert block["people"] == []


def test_the_period_includes_both_its_end_days(directory, db, npi):
    created = create(directory, npi, npi["ravi"], "A")
    db.query(Task).filter(Task.id == created["id"]).update({"created_at": at(date(2026, 10, 12))})
    db.commit()

    def assigned(start, end):
        return report(directory, npi["asha"], f"?from={start}&to={end}")["period"]["totals"]["assigned"]

    assert assigned("2026-10-12", "2026-10-12") == 1  # from == to == the day itself
    assert assigned("2026-10-11", "2026-10-12") == 1  # the last day counts
    assert assigned("2026-10-12", "2026-10-13") == 1  # the first day counts
    assert assigned("2026-10-13", "2026-10-14") == 0
    assert assigned("2026-10-10", "2026-10-11") == 0


def test_a_task_with_no_owner_counts_in_the_totals_but_has_no_person_row(directory, db, npi):
    create(directory, npi, npi["ravi"], "Owned")
    orphan = create(directory, npi, npi["ravi"], "Ownerless")
    db.query(Task).filter(Task.id == orphan["id"]).update({"assignee_id": None})
    db.commit()
    today = date.today().isoformat()

    result = report(directory, npi["asha"], f"?from={today}&to={today}")

    assert result["all_time"]["totals"]["todo"] == 2
    assert [p["counts"]["todo"] for p in result["all_time"]["people"]] == [1]


def test_someone_who_left_still_appears_in_the_report_for_the_work_they_had(directory, db, npi):
    create(directory, npi, npi["ravi"], "Theirs")
    ravi = db.get(Person, npi["ravi"].id)
    ravi.active = False
    db.commit()
    today = date.today().isoformat()

    result = report(directory, npi["asha"], f"?from={today}&to={today}")

    [row] = result["all_time"]["people"]
    assert (row["person"]["name"], row["person"]["active"], row["counts"]["todo"]) == ("Ravi", False, 1)


def test_rates_stay_between_zero_and_one_hundred_percent_for_work_closed_in_the_period(directory, npi):
    for title in ("A", "B", "C"):
        finish(directory, npi, create(directory, npi, npi["ravi"], title))
    today = date.today().isoformat()

    totals = report(directory, npi["asha"], f"?from={today}&to={today}")["period"]["totals"]

    assert (totals["assigned"], totals["done"], totals["completion_rate"]) == (3, 3, 1.0)
    assert 0 <= totals["avg_days_to_close"] <= 1
