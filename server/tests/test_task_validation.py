"""Bad and borderline input to the task endpoints. Each limit is tested on both sides: the largest value that is
accepted and the first one that is refused. A refused request must also leave nothing behind (see
test_task_side_effects.py for the database-level proof). The caller is always the team's own manager, so every
refusal here is about the input, not permission."""
import uuid
from datetime import date, timedelta

import pytest

from models import Task, TaskActivity

NOBODY = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def asha(npi):
    return npi["asha"]


def new_task(directory, npi, **fields):
    body = {"title": "Wire harness", "assignee_id": str(npi["ravi"].id), **fields}
    return directory.call(npi["asha"], "POST", "/tasks", json=body)


def made(directory, npi):
    res = new_task(directory, npi)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def code(res) -> str:
    return res.json()["detail"]["code"]


# ---- create: the limits, on both sides ----

@pytest.mark.parametrize("title,expected", [("x", 201), ("x" * 140, 201), ("x" * 141, 422), ("", 422), ("   ", 422)],
                         ids=["one char", "140 chars", "141 chars", "empty", "only spaces"])
def test_title_limits(directory, npi, title, expected):
    assert new_task(directory, npi, title=title).status_code == expected


def test_the_title_is_trimmed(directory, npi):
    assert new_task(directory, npi, title="  Wire harness  ").json()["title"] == "Wire harness"


@pytest.mark.parametrize("size,expected", [(0, 201), (5000, 201), (5001, 422)], ids=["empty", "5000", "5001"])
def test_description_limits(directory, npi, size, expected):
    assert new_task(directory, npi, description="d" * size).status_code == expected


@pytest.mark.parametrize("priority,expected", [("low", 201), ("medium", 201), ("high", 201), ("urgent", 422), ("HIGH", 422), ("", 422), (None, 422)])
def test_priority_must_be_one_of_the_three(directory, npi, priority, expected):
    assert new_task(directory, npi, priority=priority).status_code == expected


def test_priority_defaults_to_medium_and_description_to_empty(directory, npi):
    task = new_task(directory, npi).json()

    assert (task["priority"], task["description"], task["due_at"]) == ("medium", "", None)


@pytest.mark.parametrize("due,expected", [
    ("2026-10-30", 201), (None, 201), ("2028-02-29", 201),
    ("2026-02-30", 422), ("30/10/2026", 422), ("2026-13-01", 422), ("", 422), ("soon", 422),
], ids=["a date", "none", "leap day", "no such day", "wrong format", "no such month", "empty", "text"])
def test_due_date_must_be_a_real_date_or_null(directory, npi, due, expected):
    assert new_task(directory, npi, due_at=due).status_code == expected


def _day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


@pytest.mark.parametrize("offset,expected", [(-1, 422), (-365, 422), (0, 201), (1, 201), (3650, 201)],
                         ids=["yesterday", "last year", "today", "tomorrow", "ten years out"])
def test_a_new_task_cannot_be_due_in_the_past(directory, npi, offset, expected):
    res = new_task(directory, npi, due_at=_day(offset))

    assert res.status_code == expected
    if expected == 422:
        assert res.json()["detail"]["code"] == "due_date_past"


def test_a_refused_past_date_creates_nothing(directory, npi):
    new_task(directory, npi, due_at=_day(-1))

    assert directory.call(npi["asha"], "GET", "/board").json()["tasks"] == []


def test_editing_cannot_move_the_due_date_into_the_past(directory, npi):
    task = new_task(directory, npi, due_at=_day(5)).json()

    res = directory.call(npi["asha"], "PATCH", f"/tasks/{task['id']}", json={"due_at": _day(-2)})

    assert res.status_code == 422 and res.json()["detail"]["code"] == "due_date_past"
    assert directory.call(npi["asha"], "GET", f"/tasks/{task['id']}").json()["task"]["due_at"] == _day(5)


def test_an_edit_may_keep_an_old_date_that_has_since_passed_or_clear_it(directory, db, npi):
    task = new_task(directory, npi, due_at=_day(5)).json()
    db.get(Task, uuid.UUID(task["id"])).due_at = date.today() - timedelta(days=3)  # time passed since it was set
    db.commit()

    kept = directory.call(npi["asha"], "PATCH", f"/tasks/{task['id']}", json={"title": "Renamed"})
    cleared = directory.call(npi["asha"], "PATCH", f"/tasks/{task['id']}", json={"due_at": None})

    assert kept.status_code == 200 and cleared.status_code == 200
    assert cleared.json()["due_at"] is None


def test_a_task_needs_a_title_and_an_assignee(directory, npi):
    no_title = directory.call(npi["asha"], "POST", "/tasks", json={"assignee_id": str(npi["ravi"].id)})
    no_assignee = directory.call(npi["asha"], "POST", "/tasks", json={"title": "x"})
    nothing = directory.call(npi["asha"], "POST", "/tasks", json={})

    assert (no_title.status_code, no_assignee.status_code, nothing.status_code) == (422, 422, 422)


def test_the_assignee_must_be_a_real_active_person_on_the_team(directory, npi, db):
    unknown = directory.call(npi["asha"], "POST", "/tasks", json={"title": "x", "assignee_id": NOBODY})
    garbage = directory.call(npi["asha"], "POST", "/tasks", json={"title": "x", "assignee_id": "not-a-uuid"})
    off_team = new_task(directory, npi, assignee_id=str(npi["zoe"].id))

    assert (unknown.status_code, code(unknown)) == (404, "person_not_found")
    assert garbage.status_code == 422
    assert (off_team.status_code, code(off_team)) == (422, "invalid_assignee")


def test_fields_the_client_may_not_set_are_ignored_not_applied(directory, npi, db):
    body = {"title": "x", "assignee_id": str(npi["ravi"].id), "status": "done", "team_id": NOBODY, "creator_id": NOBODY,
            "returned_count": 9, "closed_at": "2020-01-01T00:00:00Z", "accepted_at": "2020-01-01T00:00:00Z"}

    task = directory.call(npi["asha"], "POST", "/tasks", json=body).json()

    db.expire_all()
    row = db.get(Task, task["id"])
    assert (row.status, row.returned_count, row.closed_at, row.accepted_at) == ("todo", 0, None, None)
    assert str(row.team_id) == npi["team"]["id"] and row.creator_id == npi["asha"].id


# ---- edit ----

def test_an_empty_edit_changes_nothing_and_writes_no_timeline_entry(directory, npi, db):
    task_id = made(directory, npi)

    res = directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json={})

    assert res.status_code == 200
    assert db.query(TaskActivity).filter_by(task_id=task_id).count() == 1  # only "created"


def test_an_edit_cannot_reach_status_team_or_creator(directory, npi, db):
    task_id = made(directory, npi)

    directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json={"status": "done", "team_id": NOBODY, "creator_id": NOBODY, "closed_at": "2020-01-01T00:00:00Z"})

    db.expire_all()
    row = db.get(Task, task_id)
    assert (row.status, row.closed_at) == ("todo", None)
    assert str(row.team_id) == npi["team"]["id"] and row.creator_id == npi["asha"].id


@pytest.mark.parametrize("field,value", [("title", None), ("priority", None), ("description", None), ("assignee_id", None)])
def test_an_explicit_null_leaves_a_required_field_alone(directory, npi, field, value):
    task_id = made(directory, npi)

    res = directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json={field: value})

    assert res.status_code == 200
    after = res.json()
    assert after["title"] == "Wire harness" and after["assignee"]["name"] == "Ravi" and after["priority"] == "medium"


@pytest.mark.parametrize("body", [{"title": ""}, {"title": "x" * 141}, {"priority": "urgent"}, {"due_at": "soon"}, {"description": "d" * 5001}, {"assignee_id": "nope"}])
def test_an_edit_with_a_bad_value_is_refused(directory, npi, body):
    task_id = made(directory, npi)

    assert directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json=body).status_code == 422


def test_a_title_of_only_spaces_is_refused_by_the_service(directory, npi):
    task_id = made(directory, npi)

    res = directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json={"title": "   "})

    assert (res.status_code, code(res)) == (422, "title_required")


def test_a_finished_task_can_be_neither_edited_nor_reassigned(directory, npi):
    # Changed on 17 Oct by decision: completed tasks are read-only. Reopen one to change it.
    task_id = made(directory, npi)
    for to in ("in_progress", "done"):
        directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": to, "note": "ok"})

    edit = directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json={"title": "Wire harness (final)"})
    reassign = directory.call(npi["asha"], "PATCH", f"/tasks/{task_id}", json={"assignee_id": str(npi["asha"].id)})

    assert (edit.status_code, code(edit)) == (409, "task_done")
    assert (reassign.status_code, code(reassign)) == (409, "task_done")


# ---- moves ----

@pytest.mark.parametrize("size,expected", [(1, 200), (500, 200), (501, 422)], ids=["1", "500", "501"])
def test_the_note_limit_on_a_move(directory, npi, size, expected):
    task_id = made(directory, npi)

    res = directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": "blocked", "note": "n" * size})

    assert res.status_code == expected


@pytest.mark.parametrize("body", [{"to": "limbo"}, {"to": ""}, {"to": None}, {}, {"to": "TODO"}, {"to": 3}])
def test_a_move_needs_a_real_status(directory, npi, body):
    task_id = made(directory, npi)

    assert directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json=body).status_code == 422


def test_moving_to_the_status_it_is_already_in_is_refused(directory, npi):
    task_id = made(directory, npi)

    res = directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": "todo"})

    assert (res.status_code, code(res)) == (409, "invalid_transition")


def test_a_reason_of_only_spaces_does_not_count(directory, npi):
    task_id = made(directory, npi)

    res = directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": "blocked", "note": "    "})

    assert (res.status_code, code(res)) == (422, "reason_required")


def test_the_reason_is_stored_trimmed(directory, npi):
    task_id = made(directory, npi)

    directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": "blocked", "note": "  waiting on supplier  "})

    entry = directory.call(npi["asha"], "GET", f"/tasks/{task_id}").json()["timeline"][-1]
    assert entry["note"] == "waiting on supplier"


# ---- comments ----

@pytest.mark.parametrize("body,expected", [("c", 201), ("c" * 1000, 201), ("c" * 1001, 422), ("", 422), ("   ", 422)],
                         ids=["one char", "1000", "1001", "empty", "only spaces"])
def test_comment_limits(directory, npi, body, expected):
    task_id = made(directory, npi)

    assert directory.call(npi["asha"], "POST", f"/tasks/{task_id}/comments", json={"body": body}).status_code == expected


def test_a_comment_needs_a_body_field(directory, npi):
    task_id = made(directory, npi)

    assert directory.call(npi["asha"], "POST", f"/tasks/{task_id}/comments", json={}).status_code == 422
    assert directory.call(npi["asha"], "POST", f"/tasks/{task_id}/comments", json={"text": "hi"}).status_code == 422


# ---- ids ----

@pytest.mark.parametrize("method,path,body", [
    ("GET", "/tasks/not-a-uuid", None),
    ("PATCH", "/tasks/not-a-uuid", {"title": "x"}),
    ("DELETE", "/tasks/not-a-uuid", None),
    ("POST", "/tasks/not-a-uuid/status", {"to": "in_progress"}),
    ("POST", "/tasks/not-a-uuid/comments", {"body": "x"}),
    ("GET", "/board?team=not-a-uuid", None),
    ("GET", "/board?person=not-a-uuid", None),
])
def test_a_malformed_id_is_422(directory, asha, method, path, body):
    kwargs = {"json": body} if body is not None else {}

    assert directory.call(asha, method, path, **kwargs).status_code == 422


@pytest.mark.parametrize("method,path,body", [
    ("GET", f"/tasks/{NOBODY}", None),
    ("PATCH", f"/tasks/{NOBODY}", {"title": "x"}),
    ("DELETE", f"/tasks/{NOBODY}", None),
    ("POST", f"/tasks/{NOBODY}/status", {"to": "in_progress"}),
    ("POST", f"/tasks/{NOBODY}/comments", {"body": "x"}),
])
def test_a_task_that_does_not_exist_is_404(directory, asha, method, path, body):
    kwargs = {"json": body} if body is not None else {}

    res = directory.call(asha, method, path, **kwargs)

    assert (res.status_code, code(res)) == (404, "task_not_found")


def test_a_timeline_entry_cannot_be_edited_or_deleted_through_the_api(directory, npi, db):
    task_id = made(directory, npi)
    entry = directory.call(npi["asha"], "POST", f"/tasks/{task_id}/comments", json={"body": "first"}).json()["id"]

    for method in ("PATCH", "PUT", "DELETE"):
        res = directory.call(npi["asha"], method, f"/tasks/{task_id}/comments/{entry}", json={"body": "changed"})
        assert res.status_code in (404, 405), method

    db.expire_all()
    assert db.get(TaskActivity, entry).note == "first"


# ---- board and report query values ----

def test_the_board_ignores_empty_filter_pieces_but_refuses_unknown_ones(directory, asha):
    assert directory.call(asha, "GET", "/board?filter=").status_code == 200
    assert directory.call(asha, "GET", "/board?filter=,overdue,").status_code == 200
    assert directory.call(asha, "GET", "/board?filter=overdue,bogus").json()["detail"]["code"] == "unknown_filter"


def test_attention_must_be_a_boolean(directory, asha):
    assert directory.call(asha, "GET", "/board?attention=true").status_code == 200
    assert directory.call(asha, "GET", "/board?attention=false").status_code == 200
    assert directory.call(asha, "GET", "/board?attention=maybe").status_code == 422


def test_a_person_filter_for_someone_who_is_not_on_the_team_gives_an_empty_board_not_an_error(directory, npi):
    res = directory.call(npi["asha"], "GET", f"/board?person={npi['zoe'].id}")

    assert res.status_code == 200
    assert res.json()["tasks"] == [] and res.json()["stats"]["todo"] == 0
