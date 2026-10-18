"""GET /reports/all-teams: the admin's report across every team at once."""
from datetime import date

import pytest

from models import Person, Task
from tests.conftest import make_team


@pytest.fixture
def two_teams(db, directory, admin, npi):
    """NPI (Asha manages, Ravi is a member) with 3 tasks, one done; QA (Omar manages, Priya is a member) with 1; Empty (Eve) with none."""
    omar, priya, eve = directory.person("Omar"), directory.person("Priya"), directory.person("Eve")
    qa = make_team(directory, admin, "QA", omar)
    make_team(directory, admin, "Empty", eve)
    directory.call(omar, "POST", f"/teams/{qa['id']}/members", json={"person_id": str(priya.id)})
    db.expire_all()

    def add(manager, assignee, title, *, finish=False):
        task = directory.call(manager, "POST", "/tasks", json={"title": title, "assignee_id": str(assignee.id)}).json()
        if finish:
            for to in ("in_progress", "done"):
                assert directory.call(manager, "POST", f"/tasks/{task['id']}/status", json={"to": to, "note": "ok"}).status_code == 200
        return task

    add(npi["asha"], npi["ravi"], "NPI one")
    add(npi["asha"], npi["ravi"], "NPI two")
    add(npi["asha"], npi["asha"], "NPI three", finish=True)
    add(omar, priya, "QA one")
    return {"omar": omar, "priya": priya, "eve": eve}


def all_teams(directory, who, query=None):
    today = date.today().isoformat()
    return directory.call(who, "GET", f"/reports/all-teams?from={today}&to={today}{query or ''}")


def test_an_admin_gets_one_row_per_team_by_name_with_each_managers_name(directory, admin, two_teams):
    res = all_teams(directory, admin)

    assert res.status_code == 200, res.text
    rows = res.json()["all_time"]["teams"]
    assert [(r["team"]["name"], (r["team"]["manager"] or {}).get("name")) for r in rows] == [
        ("Empty", "Eve"), ("NPI", "Asha"), ("QA", "Omar")]


def test_each_row_has_that_teams_numbers_and_the_total_is_their_sum(directory, admin, two_teams):
    body = all_teams(directory, admin).json()

    rows = {r["team"]["name"]: r["counts"] for r in body["all_time"]["teams"]}
    assert (rows["NPI"]["todo"], rows["NPI"]["done"], rows["NPI"]["assigned"]) == (2, 1, 3)
    assert (rows["QA"]["todo"], rows["QA"]["done"], rows["QA"]["assigned"]) == (1, 0, 1)
    totals = body["all_time"]["totals"]
    for field in ("todo", "in_progress", "blocked", "review", "overdue", "assigned", "done", "returned"):
        assert totals[field] == sum(r[field] for r in rows.values()), field
    assert (totals["todo"], totals["done"], totals["assigned"]) == (3, 1, 4)


def test_each_team_lists_its_own_people_with_their_numbers(directory, admin, two_teams):
    rows = {r["team"]["name"]: r for r in all_teams(directory, admin).json()["all_time"]["teams"]}

    npi_people = {p["person"]["name"]: p["counts"] for p in rows["NPI"]["people"]}
    assert list(npi_people) == ["Asha", "Ravi"]  # by name; only people who have NPI tasks
    assert (npi_people["Ravi"]["todo"], npi_people["Ravi"]["done"]) == (2, 0)
    assert (npi_people["Asha"]["todo"], npi_people["Asha"]["done"]) == (0, 1)
    assert [p["person"]["name"] for p in rows["QA"]["people"]] == ["Priya"]
    assert rows["Empty"]["people"] == []  # a team with no tasks has nobody to list
    # a person's rows add up to the team row
    assert sum(p["counts"]["todo"] for p in rows["NPI"]["people"]) == rows["NPI"]["counts"]["todo"]


def test_a_team_with_no_tasks_still_gets_a_row_of_zeros(directory, admin, two_teams):
    [empty] = [r for r in all_teams(directory, admin).json()["all_time"]["teams"] if r["team"]["name"] == "Empty"]

    assert empty["counts"]["assigned"] == 0 and empty["counts"]["todo"] == 0
    assert (empty["counts"]["completion_rate"], empty["counts"]["on_time_rate"]) == (None, None)


def test_the_period_block_follows_the_same_rules_as_the_team_report(directory, admin, two_teams):
    long_ago = "2020-01-01"

    body = directory.call(admin, "GET", f"/reports/all-teams?from={long_ago}&to={long_ago}").json()

    assert body["period"]["totals"]["assigned"] == 0 and body["period"]["totals"]["todo"] == 3  # open work is the current state
    assert body["all_time"]["totals"]["assigned"] == 4
    assert [r["counts"]["assigned"] for r in body["period"]["teams"]] == [0, 0, 0]


def test_the_totals_equal_the_sum_of_the_separate_team_reports(directory, admin, two_teams, npi):
    today = date.today().isoformat()
    separate = {}
    for team_id, name in ((npi["team"]["id"], "NPI"),):
        separate[name] = directory.call(admin, "GET", f"/reports/team?from={today}&to={today}&team={team_id}").json()["all_time"]["totals"]
    all_rows = {r["team"]["name"]: r["counts"] for r in all_teams(directory, admin).json()["all_time"]["teams"]}

    assert all_rows["NPI"] == separate["NPI"]  # the same numbers, whichever way you ask


def test_only_an_admin_may_ask(directory, npi, two_teams):
    assert all_teams(directory, None).status_code == 401
    assert all_teams(directory, npi["ravi"]).status_code == 403  # cannot sign in
    for manager in (npi["asha"], two_teams["omar"]):
        res = all_teams(directory, manager)
        assert (res.status_code, res.json()["detail"]["code"]) == (403, "forbidden")


def test_a_backwards_or_malformed_range_is_refused(directory, admin, two_teams):
    backwards = directory.call(admin, "GET", "/reports/all-teams?from=2026-10-18&to=2026-10-12")
    junk = directory.call(admin, "GET", "/reports/all-teams?from=yesterday&to=today")
    missing = directory.call(admin, "GET", "/reports/all-teams")

    assert (backwards.status_code, backwards.json()["detail"]["code"]) == (422, "invalid_range")
    assert junk.status_code == 422 and missing.status_code == 422


def test_a_team_that_was_deleted_is_gone_from_the_report_and_its_tasks_from_the_totals(directory, admin, two_teams, db):
    qa = next(r for r in all_teams(directory, admin).json()["all_time"]["teams"] if r["team"]["name"] == "QA")["team"]["id"]

    assert directory.call(admin, "DELETE", f"/teams/{qa}", json={"confirm_name": "QA", "reason": "wound up"}).status_code == 204

    body = all_teams(directory, admin).json()
    assert [r["team"]["name"] for r in body["all_time"]["teams"]] == ["Empty", "NPI"]
    assert body["all_time"]["totals"]["assigned"] == 3


def test_asking_changes_nothing(directory, admin, two_teams, db):
    before = sorted((str(t.id), t.status, t.updated_at) for t in db.query(Task)), sorted((str(p.id), p.active) for p in db.query(Person))

    all_teams(directory, admin)

    db.expire_all()
    assert (sorted((str(t.id), t.status, t.updated_at) for t in db.query(Task)), sorted((str(p.id), p.active) for p in db.query(Person))) == before
