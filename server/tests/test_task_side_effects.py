"""The unintended must not happen. These tests look at the database before and after, not just at the response:
a refused request leaves every task and timeline entry exactly as it was, a read writes nothing, and an action on
one task or team never touches another."""
from datetime import date

import pytest
from sqlalchemy import text

from models import Person, Task, TaskActivity
from tests.conftest import make_team

NOBODY = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def world(db, directory, admin, npi):
    """NPI (Asha manages; Ravi, Zoe is on no team) and QA (Omar manages, Priya is a member), each with tasks."""
    omar, priya = directory.person("Omar"), directory.person("Priya")
    qa = make_team(directory, admin, "QA", omar)
    directory.call(omar, "POST", f"/teams/{qa['id']}/members", json={"person_id": str(priya.id)})

    def create(manager, assignee, title):
        res = directory.call(manager, "POST", "/tasks", json={"title": title, "assignee_id": str(assignee.id)})
        assert res.status_code == 201, res.text
        return res.json()["id"]

    ids = {"a1": create(npi["asha"], npi["ravi"], "NPI one"), "a2": create(npi["asha"], npi["ravi"], "NPI two"),
           "q1": create(omar, priya, "QA one")}
    db.expire_all()
    return {"omar": omar, "priya": priya, "qa": qa, "ids": ids}


def snapshot(db):
    """Every task field and every timeline entry, as plain values, so two snapshots can be compared."""
    db.expire_all()
    tasks = {
        str(t.id): (t.team_id, t.title, t.description, t.status, t.priority, t.due_at, t.creator_id, t.assignee_id,
                    t.returned_count, t.accepted_at, t.created_at, t.updated_at, t.closed_at)
        for t in db.query(Task)
    }
    timeline = sorted(
        (str(a.task_id), str(a.id), a.actor_id, a.kind, a.source, a.field, a.old_value, a.new_value, a.note, a.created_at)
        for a in db.query(TaskActivity)
    )
    return tasks, timeline


# ---- refused requests leave nothing behind ----

REFUSED = [
    # (label, caller, method, path, body)
    ("admin edits", "admin", "PATCH", "/tasks/{a1}", {"title": "hijacked"}),
    ("admin moves", "admin", "POST", "/tasks/{a1}/status", {"to": "in_progress"}),
    ("admin deletes", "admin", "DELETE", "/tasks/{a1}", None),
    ("other manager edits", "omar", "PATCH", "/tasks/{a1}", {"title": "hijacked"}),
    ("other manager moves", "omar", "POST", "/tasks/{a1}/status", {"to": "in_progress"}),
    ("other manager comments", "omar", "POST", "/tasks/{a1}/comments", {"body": "hi"}),
    ("other manager deletes", "omar", "DELETE", "/tasks/{a1}", None),
    ("plain member edits", "ravi", "PATCH", "/tasks/{a1}", {"title": "hijacked"}),
    ("nobody moves", None, "POST", "/tasks/{a1}/status", {"to": "in_progress"}),
    ("move that is not allowed", "asha", "POST", "/tasks/{a1}/status", {"to": "done", "note": "skipping ahead"}),
    ("move to the same status", "asha", "POST", "/tasks/{a1}/status", {"to": "todo"}),
    ("block without a reason", "asha", "POST", "/tasks/{a1}/status", {"to": "blocked"}),
    ("block with a blank reason", "asha", "POST", "/tasks/{a1}/status", {"to": "blocked", "note": "  "}),
    ("move to a status that does not exist", "asha", "POST", "/tasks/{a1}/status", {"to": "limbo"}),
    ("blank comment", "asha", "POST", "/tasks/{a1}/comments", {"body": "   "}),
    ("edit with a bad priority", "asha", "PATCH", "/tasks/{a1}", {"priority": "urgent", "title": "half applied?"}),
    ("edit with a blank title", "asha", "PATCH", "/tasks/{a1}", {"title": "   "}),
    ("edit with an assignee from another team", "asha", "PATCH", "/tasks/{a1}", {"assignee_id": "{priya}", "title": "half applied?"}),
    ("edit with an assignee that does not exist", "asha", "PATCH", "/tasks/{a1}", {"assignee_id": NOBODY, "title": "half applied?"}),
    ("create with an assignee from another team", "asha", "POST", "/tasks", {"title": "x", "assignee_id": "{priya}"}),
    ("create with a blank title", "asha", "POST", "/tasks", {"title": "  ", "assignee_id": "{ravi}"}),
    ("create with a bad date", "asha", "POST", "/tasks", {"title": "x", "assignee_id": "{ravi}", "due_at": "soon"}),
    ("create by someone on no team", "admin", "POST", "/tasks", {"title": "x", "assignee_id": "{ravi}"}),
]


@pytest.mark.parametrize("label,caller,method,path,body", REFUSED, ids=[r[0] for r in REFUSED])
def test_a_refused_request_changes_nothing(directory, db, npi, admin, world, label, caller, method, path, body):
    callers = {"admin": admin, "omar": world["omar"], "ravi": npi["ravi"], "asha": npi["asha"], None: None}
    names = {**world["ids"], "priya": str(world["priya"].id), "ravi": str(npi["ravi"].id)}

    def fill(value):
        return value.format(**names) if isinstance(value, str) else value

    body = {k: fill(v) for k, v in body.items()} if body else None
    before = snapshot(db)

    res = directory.call(callers[caller], method, path.format(**names), **({"json": body} if body else {}))

    assert 400 <= res.status_code < 500, f"{label}: expected a refusal, got {res.status_code}"
    assert snapshot(db) == before, f"{label}: the refusal still changed something"


def test_a_move_refused_on_a_finished_task_leaves_its_close_time_alone(directory, db, npi):
    task_id = directory.call(npi["asha"], "POST", "/tasks", json={"title": "x", "assignee_id": str(npi["ravi"].id)}).json()["id"]
    for to in ("in_progress", "done"):
        directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": to, "note": "ok"})
    before = snapshot(db)

    again = directory.call(npi["asha"], "POST", f"/tasks/{task_id}/status", json={"to": "done", "note": "again"})

    assert again.status_code == 409
    assert snapshot(db) == before


# ---- reading writes nothing ----

def test_reading_the_board_a_task_and_the_report_changes_nothing(directory, db, npi, admin, world):
    before = snapshot(db)
    today = date.today().isoformat()
    team = npi["team"]["id"]

    for who in (npi["asha"], admin):
        for path in (f"/board?team={team}", f"/board?team={team}&attention=true&filter=overdue", f"/tasks/{world['ids']['a1']}",
                     f"/reports/team?from={today}&to={today}&team={team}", "/me"):
            assert directory.call(who, "GET", path).status_code == 200, path
    directory.call(None, "GET", "/dev/accounts")

    assert snapshot(db) == before


# ---- an action on one task or team never touches another ----

def test_moving_commenting_and_editing_one_task_leaves_the_others_alone(directory, db, npi, world):
    others_before = {k: v for k, v in snapshot(db)[0].items() if k != world["ids"]["a1"]}
    timeline_before = [e for e in snapshot(db)[1] if e[0] != world["ids"]["a1"]]
    a1 = world["ids"]["a1"]

    directory.call(npi["asha"], "POST", f"/tasks/{a1}/status", json={"to": "blocked", "note": "waiting"})
    directory.call(npi["asha"], "POST", f"/tasks/{a1}/comments", json={"body": "chasing the supplier"})
    directory.call(npi["asha"], "PATCH", f"/tasks/{a1}", json={"title": "NPI one (renamed)", "priority": "high"})

    tasks, timeline = snapshot(db)
    assert {k: v for k, v in tasks.items() if k != a1} == others_before
    assert [e for e in timeline if e[0] != a1] == timeline_before


def test_deleting_a_task_leaves_every_other_task_and_timeline(directory, db, npi, world):
    ids = world["ids"]
    others_before = {k: v for k, v in snapshot(db)[0].items() if k != ids["a1"]}
    timeline_before = [e for e in snapshot(db)[1] if e[0] != ids["a1"]]

    assert directory.call(npi["asha"], "DELETE", f"/tasks/{ids['a1']}").status_code == 204

    tasks, timeline = snapshot(db)
    assert tasks == others_before and timeline == timeline_before


def test_editing_the_title_changes_nothing_else_about_the_task(directory, db, npi, world):
    a1 = world["ids"]["a1"]
    directory.call(npi["asha"], "POST", f"/tasks/{a1}/status", json={"to": "in_progress"})
    before = snapshot(db)[0][a1]
    fields = ("team_id", "title", "description", "status", "priority", "due_at", "creator_id", "assignee_id",
              "returned_count", "accepted_at", "created_at", "updated_at", "closed_at")

    directory.call(npi["asha"], "PATCH", f"/tasks/{a1}", json={"title": "Renamed"})

    after = dict(zip(fields, snapshot(db)[0][a1]))
    changed = {name for name, old in zip(fields, before) if after[name] != old}
    assert changed == {"title", "updated_at"}


def test_deleting_a_team_erases_its_tasks_and_only_its_tasks(directory, db, admin, npi, world):
    qa_ids = [world["ids"]["q1"]]
    npi_before = {k: v for k, v in snapshot(db)[0].items() if k not in qa_ids}
    npi_timeline = [e for e in snapshot(db)[1] if e[0] not in qa_ids]

    res = directory.call(admin, "DELETE", f"/teams/{world['qa']['id']}", json={"confirm_name": "QA", "reason": "wound up"})

    assert res.status_code == 204
    tasks, timeline = snapshot(db)
    assert tasks == npi_before and timeline == npi_timeline
    assert db.query(TaskActivity).filter(TaskActivity.task_id.in_(qa_ids)).count() == 0


def test_taking_someone_off_the_team_keeps_their_tasks_exactly_as_they_were(directory, db, npi, world):
    before = snapshot(db)

    res = directory.call(npi["asha"], "DELETE", f"/teams/{npi['team']['id']}/members/{npi['ravi'].id}")

    assert res.status_code == 204
    assert snapshot(db) == before  # same assignee, same status, same timeline: they just now need a new owner
    board = directory.call(npi["asha"], "GET", "/board").json()
    assert {t["title"] for t in board["orphans"]} == {"NPI one", "NPI two"}


def test_a_person_who_left_the_directory_keeps_their_tasks_and_cannot_be_given_new_ones(directory, db, npi, world):
    ravi = db.get(Person, npi["ravi"].id)
    ravi.active = False  # what the directory load does for someone missing from the Slack file
    db.commit()
    before = snapshot(db)

    new = directory.call(npi["asha"], "POST", "/tasks", json={"title": "x", "assignee_id": str(ravi.id)})
    existing = directory.call(npi["asha"], "GET", f"/tasks/{world['ids']['a1']}").json()["task"]

    assert (new.status_code, new.json()["detail"]["code"]) == (422, "invalid_assignee")
    assert existing["needs_reassignment"] is True and existing["assignee"]["name"] == "Ravi"
    assert snapshot(db) == before


def test_a_reassignment_moves_only_that_one_task(directory, db, npi, world):
    a1, a2 = world["ids"]["a1"], world["ids"]["a2"]

    directory.call(npi["asha"], "PATCH", f"/tasks/{a1}", json={"assignee_id": str(npi["asha"].id)})

    tasks = snapshot(db)[0]
    assert tasks[a1][7] == npi["asha"].id and tasks[a2][7] == npi["ravi"].id  # index 7 is assignee_id


def test_the_send_back_counter_moves_only_on_a_send_back(directory, db, npi, world):
    a1 = world["ids"]["a1"]

    def move(to, note=None):
        assert directory.call(npi["asha"], "POST", f"/tasks/{a1}/status", json={"to": to, "note": note}).status_code == 200
        db.expire_all()
        return db.get(Task, a1).returned_count

    assert move("in_progress") == 0
    assert move("review") == 0
    assert move("in_progress", "needs rework") == 1  # the send back
    assert move("todo", "paused") == 1  # moving back is not a send back
    assert move("in_progress") == 1
    assert move("done", "shipped") == 1
    assert move("in_progress", "found a defect") == 1  # reopening is not a send back


def test_the_close_time_exists_only_while_a_task_is_done(directory, db, npi, world):
    a1 = world["ids"]["a1"]

    def closed_at():
        db.expire_all()
        return db.get(Task, a1).closed_at

    assert closed_at() is None
    for to in ("in_progress", "review"):
        directory.call(npi["asha"], "POST", f"/tasks/{a1}/status", json={"to": to})
        assert closed_at() is None
    directory.call(npi["asha"], "POST", f"/tasks/{a1}/status", json={"to": "done", "note": "ok"})
    assert closed_at() is not None
    directory.call(npi["asha"], "POST", f"/tasks/{a1}/status", json={"to": "in_progress", "note": "reopened"})
    assert closed_at() is None


def test_the_timeline_only_grows(directory, db, npi, world):
    a1 = world["ids"]["a1"]
    seen = [e[1] for e in snapshot(db)[1] if e[0] == a1]  # the "created" entry is already there
    assert len(seen) == 1

    for step in range(4):
        directory.call(npi["asha"], "POST", f"/tasks/{a1}/comments", json={"body": f"note {step}"})
        entries = [e[1] for e in snapshot(db)[1] if e[0] == a1]
        assert set(seen) <= set(entries) and len(entries) == len(seen) + 1
        seen = entries


def test_the_database_itself_refuses_to_rewrite_the_timeline(db, world):
    with pytest.raises(Exception, match="append-only"):
        db.execute(text("UPDATE task_activity SET note = 'rewritten'"))
    db.rollback()
