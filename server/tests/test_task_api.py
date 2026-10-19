"""The task endpoints end to end: board, create, detail, edit, move, comment, delete."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from core.exceptions import AppError
from models import Task
from tasks.services import queries
from tests.conftest import make_team


def create(directory, npi, **fields):
    body = {"title": "Wire harness", "assignee_id": str(npi["ravi"].id), **fields}
    res = directory.call(npi["asha"], "POST", "/tasks", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def move(directory, npi, task, to, note=None):
    res = directory.call(npi["asha"], "POST", f"/tasks/{task['id']}/status", json={"to": to, "note": note})
    assert res.status_code == 200, res.text
    return res.json()


def board(directory, who, query=""):
    res = directory.call(who, "GET", f"/board{query}")
    assert res.status_code == 200, res.text
    return res.json()


# ---- create and read ----

def test_create_returns_the_task_with_the_actions_its_manager_has(directory, npi):
    task = create(directory, npi, priority="high", due_at="2026-10-30")

    assert (task["status"], task["priority"], task["due_at"], task["assignee"]["name"], task["creator"]["name"]) == (
        "todo", "high", "2026-10-30", "Ravi", "Asha",
    )
    actions = task["actions"]
    assert (actions["can_edit"], actions["can_delete"], actions["can_comment"]) == (True, True, True)
    assert {t["to"] for t in actions["transitions"]} == {"in_progress", "blocked"}


def test_the_board_lists_the_teams_cards_with_people_and_counts(directory, npi):
    create(directory, npi, title="A")
    create(directory, npi, title="B")

    result = board(directory, npi["asha"])

    assert [t["title"] for t in result["tasks"]] == ["A", "B"]
    assert result["team"]["name"] == "NPI" and result["read_only"] is False
    assert {p["name"] for p in result["people"]} == {"Asha", "Ravi"}
    assert result["stats"] == {"todo": 2, "in_progress": 0, "blocked": 0, "overdue": 0, "done": 0}


def test_an_admin_reads_any_board_and_may_only_comment(directory, admin, npi):
    task = create(directory, npi)

    result = board(directory, admin, f"?team={npi['team']['id']}")

    assert result["read_only"] is True
    [card] = result["tasks"]
    assert card["actions"] == {"can_edit": False, "can_delete": False, "can_change_assignee": False, "can_comment": True, "transitions": []}  # commenting is the one thing an admin may do
    assert directory.call(admin, "GET", f"/tasks/{task['id']}").status_code == 200


def test_an_admin_with_no_team_must_choose_one_and_a_manager_cannot_peek(directory, admin, npi):
    other = directory.person("Omar")
    qa = make_team(directory, admin, "QA", other)

    assert directory.call(admin, "GET", "/board").json()["detail"]["code"] == "choose_team"
    peek = directory.call(npi["asha"], "GET", f"/board?team={qa['id']}")
    assert (peek.status_code, peek.json()["detail"]["code"]) == (403, "forbidden")
    missing = directory.call(admin, "GET", "/board?team=00000000-0000-0000-0000-000000000000")
    assert missing.json()["detail"]["code"] == "team_not_found"


def test_a_manager_cannot_open_another_teams_task(directory, admin, npi):
    task = create(directory, npi)
    other = directory.person("Omar")
    make_team(directory, admin, "QA", other)

    assert directory.call(other, "GET", f"/tasks/{task['id']}").status_code == 403
    assert directory.call(other, "PATCH", f"/tasks/{task['id']}", json={"title": "x"}).status_code == 403


# ---- filters, attention, stats ----

def test_filters_and_the_attention_tick_narrow_the_cards_and_say_how_many(directory, db, npi):
    ok = create(directory, npi, title="Quiet", due_at=(datetime.now().date() + timedelta(days=20)).isoformat())
    blocked = create(directory, npi, title="Stuck")
    move(directory, npi, blocked, "blocked", "waiting on supplier")
    late = create(directory, npi, title="Late", due_at=(datetime.now().date() + timedelta(days=1)).isoformat())
    # A due date cannot be set in the past, so a task only becomes overdue as time passes: backdate it here.
    db.get(Task, uuid.UUID(late["id"])).due_at = date(2020, 1, 1)
    db.commit()

    everything = board(directory, npi["asha"])
    attention = board(directory, npi["asha"], "?attention=true")
    only_blocked = board(directory, npi["asha"], "?filter=blocked")

    assert len(everything["tasks"]) == 3 and everything["attention_count"] == 2
    assert {t["title"] for t in attention["tasks"]} == {"Stuck", "Late"}
    assert [t["title"] for t in only_blocked["tasks"]] == ["Stuck"]
    assert everything["filter_counts"] == {"needs_review": 0, "overdue": 1, "blocked": 1, "due_week": 0}
    assert everything["stats"]["overdue"] == 1 and ok and late


def test_the_person_dropdown_and_an_unknown_filter(directory, npi):
    create(directory, npi, title="Ravi's")
    create(directory, npi, title="Asha's", assignee_id=str(npi["asha"].id))

    mine = board(directory, npi["asha"], f"?person={npi['asha'].id}")

    assert [t["title"] for t in mine["tasks"]] == ["Asha's"]
    assert directory.call(npi["asha"], "GET", "/board?filter=nonsense").json()["detail"]["code"] == "unknown_filter"


def test_done_cards_stay_on_the_board_the_most_recently_closed_first_after_the_open_ones(directory, db, npi):
    first, second, open_card = create(directory, npi, title="First"), create(directory, npi, title="Second"), create(directory, npi, title="Open")
    for task in (first, second):
        move(directory, npi, task, "in_progress")
    move(directory, npi, second, "done", "shipped")
    move(directory, npi, first, "done", "shipped")
    # Closed months ago: still on the board. Second was closed before First, so First stays on top.
    db.query(Task).filter(Task.title == "Second").update({"closed_at": datetime.now(timezone.utc) - timedelta(days=90)})
    db.commit()

    result = board(directory, npi["asha"])

    assert [t["title"] for t in result["tasks"]] == ["Open", "First", "Second"]
    assert result["stats"]["done"] == 2 and open_card


def test_removing_the_assignee_from_the_team_makes_the_task_an_orphan(directory, npi):
    task = create(directory, npi)

    directory.call(npi["asha"], "DELETE", f"/teams/{npi['team']['id']}/members/{npi['ravi'].id}")
    result = board(directory, npi["asha"])

    assert [t["id"] for t in result["orphans"]] == [task["id"]]
    assert result["orphans"][0]["needs_reassignment"] is True and result["attention_count"] == 1


# ---- edit, move, comment, delete ----

def test_patch_changes_only_what_is_sent_and_null_clears_the_date(directory, npi):
    task = create(directory, npi, due_at="2026-10-30", description="keep me")

    res = directory.call(npi["asha"], "PATCH", f"/tasks/{task['id']}", json={"title": "New title", "due_at": None})

    body = res.json()
    assert (body["title"], body["due_at"], body["description"]) == ("New title", None, "keep me")


def test_a_move_shows_its_reason_and_the_timeline_names_the_actor(directory, npi):
    task = create(directory, npi)
    blocked = move(directory, npi, task, "blocked", "waiting on supplier")

    assert blocked["latest_reason"]["kind"] == "blocked" and blocked["latest_reason"]["note"] == "waiting on supplier"
    detail = directory.call(npi["asha"], "GET", f"/tasks/{task['id']}").json()
    assert [e["kind"] for e in detail["timeline"]] == ["created", "status"]
    status_entry = detail["timeline"][1]
    assert (status_entry["actor"]["name"], status_entry["old_value"], status_entry["new_value"], status_entry["note"]) == (
        "Asha", "todo", "blocked", "waiting on supplier",
    )


def test_send_back_marks_the_card_returned(directory, npi):
    task = create(directory, npi)
    for to, note in (("in_progress", None), ("review", None), ("in_progress", "needs rework")):
        card = move(directory, npi, task, to, note)

    assert (card["returned"], card["returned_count"], card["latest_reason"]["kind"]) == (True, 1, "sent_back")


def test_a_move_without_its_reason_or_to_nowhere_is_refused(directory, npi):
    task = create(directory, npi)

    no_reason = directory.call(npi["asha"], "POST", f"/tasks/{task['id']}/status", json={"to": "blocked"})
    skip = directory.call(npi["asha"], "POST", f"/tasks/{task['id']}/status", json={"to": "done", "note": "x"})
    bogus = directory.call(npi["asha"], "POST", f"/tasks/{task['id']}/status", json={"to": "limbo"})

    assert (no_reason.status_code, no_reason.json()["detail"]["code"]) == (422, "reason_required")
    assert (skip.status_code, skip.json()["detail"]["code"]) == (409, "invalid_transition")
    assert bogus.status_code == 422


def test_a_comment_comes_back_as_a_timeline_entry_and_appears_in_the_detail(directory, npi):
    task = create(directory, npi)

    res = directory.call(npi["asha"], "POST", f"/tasks/{task['id']}/comments", json={"body": "Parts arrive Monday"})

    assert res.status_code == 201
    assert (res.json()["kind"], res.json()["note"], res.json()["actor"]["name"], res.json()["source"]) == (
        "comment", "Parts arrive Monday", "Asha", "workboard",
    )
    detail = directory.call(npi["asha"], "GET", f"/tasks/{task['id']}").json()
    assert [e["kind"] for e in detail["timeline"]] == ["created", "comment"]


def test_delete_answers_204_then_404_and_refuses_a_task_in_review(directory, npi):
    gone, kept = create(directory, npi), create(directory, npi)
    for to in ("in_progress", "review"):
        move(directory, npi, kept, to)

    assert directory.call(npi["asha"], "DELETE", f"/tasks/{gone['id']}").status_code == 204
    assert directory.call(npi["asha"], "GET", f"/tasks/{gone['id']}").status_code == 404
    refused = directory.call(npi["asha"], "DELETE", f"/tasks/{kept['id']}")
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "not_deletable")


def test_an_assignee_off_the_team_is_422_and_a_blank_title_is_refused(directory, npi):
    bad_assignee = directory.call(
        npi["asha"], "POST", "/tasks", json={"title": "x", "assignee_id": str(npi["zoe"].id)}
    )
    blank = directory.call(npi["asha"], "POST", "/tasks", json={"title": "   ", "assignee_id": str(npi["ravi"].id)})

    assert (bad_assignee.status_code, bad_assignee.json()["detail"]["code"]) == (422, "invalid_assignee")
    assert (blank.status_code, blank.json()["detail"]["code"]) == (422, "title_required")


def test_a_done_task_cannot_be_edited_until_it_is_reopened(directory, npi):
    task = create(directory, npi, title="Wire harness")
    move(directory, npi, task, "in_progress")
    done = move(directory, npi, task, "done", "shipped")
    assert done["actions"]["can_edit"] is False

    for patch in ({"title": "Renamed"}, {"priority": "high"}, {"due_at": None}, {"assignee_id": str(npi["asha"].id)}):
        res = directory.call(npi["asha"], "PATCH", f"/tasks/{task['id']}", json=patch)
        assert (res.status_code, res.json()["detail"]["code"]) == (409, "task_done"), patch
    assert directory.call(npi["asha"], "GET", f"/tasks/{task['id']}").json()["task"]["title"] == "Wire harness"

    reopened = move(directory, npi, task, "in_progress", "needs one more change")
    assert reopened["actions"]["can_edit"] is True
    assert directory.call(npi["asha"], "PATCH", f"/tasks/{task['id']}", json={"title": "Renamed"}).status_code == 200


def test_a_person_on_no_team_who_is_not_an_admin_has_no_board(db, npi):
    # Not reachable through the API (such a person cannot sign in), so the rule is checked where it lives.
    with pytest.raises(AppError) as err:
        queries.resolve_board_team(db, npi["zoe"], None)

    assert (err.value.status_code, err.value.code) == (403, "no_team")


def test_a_timeline_entry_that_does_not_exist_is_a_404(db, admin):
    with pytest.raises(AppError) as err:
        queries.get_activity(db, admin, uuid.uuid4())

    assert (err.value.status_code, err.value.code) == (404, "activity_not_found")


def test_a_task_whose_person_row_is_gone_has_no_summary():
    assert queries._summary(None) is None


def test_the_task_routes_need_a_signed_in_person(directory, npi):
    task = create(directory, npi)

    for method, path in (("GET", "/board"), ("GET", f"/tasks/{task['id']}"), ("POST", "/tasks")):
        assert directory.call(None, method, path).status_code == 401
