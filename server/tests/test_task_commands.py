"""Task commands (tasks/services/commands.py), called directly on a real database. Who may act is covered in
test_task_rules.py; here the point is what each command writes, refuses, and leaves on the timeline."""
import uuid
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

from core.exceptions import AppError
from models import AccessAuditLog, Task, TaskActivity
from tasks.services import commands


@contextmanager
def refused(code: str):
    """`with refused("code"):` passes only when the command fails with that exact error code."""
    with pytest.raises(AppError) as caught:
        yield
    assert caught.value.code == code


def make(db, npi, **fields) -> uuid.UUID:
    task_id = uuid.uuid4()
    args = {"title": "Wire harness", "description": "", "priority": "medium", "due_at": None, "assignee_id": npi["ravi"].id}
    commands.create_task(db, npi["asha"], task_id, **{**args, **fields})
    return task_id


def task(db, task_id) -> Task:
    db.expire_all()
    return db.get(Task, task_id)


def timeline(db, task_id) -> list[TaskActivity]:
    db.expire_all()
    return db.query(TaskActivity).filter_by(task_id=task_id).all()


def kinds(db, task_id) -> list[str]:
    return sorted(a.kind for a in timeline(db, task_id))


# ---- create ----

def test_create_puts_a_to_do_on_the_managers_team_with_a_created_entry(db, npi):
    task_id = make(db, npi, title="  Wire harness  ", description=" check ", priority="high", due_at=date(2026, 10, 30))

    t = task(db, task_id)
    assert (t.title, t.description, t.status, t.priority, t.due_at) == ("Wire harness", "check", "todo", "high", date(2026, 10, 30))
    assert (str(t.team_id), t.creator_id, t.assignee_id) == (npi["team"]["id"], npi["asha"].id, npi["ravi"].id)
    [entry] = timeline(db, task_id)
    assert (entry.kind, entry.new_value, entry.actor_id, entry.source) == ("created", "todo", npi["asha"].id, "workboard")


def test_a_manager_can_assign_to_themselves(db, npi):
    assert task(db, make(db, npi, assignee_id=npi["asha"].id)).assignee_id == npi["asha"].id


def test_create_refuses_an_assignee_off_the_team_or_inactive(db, npi):
    with refused("invalid_assignee"):
        make(db, npi, assignee_id=npi["zoe"].id)
    npi["ravi"].active = False
    db.commit()
    with refused("invalid_assignee"):
        make(db, npi, assignee_id=npi["ravi"].id)
    assert db.query(Task).count() == 0


def test_create_refuses_a_blank_title_and_anyone_but_the_manager(db, npi, admin):
    with refused("title_required"):
        make(db, npi, title="   ")
    with refused("forbidden"):  # an admin on no team has nowhere to put it
        commands.create_task(db, admin, uuid.uuid4(), "x", "", "low", None, npi["ravi"].id)
    with refused("forbidden"):  # a plain member never signs in, but the rule holds anyway
        commands.create_task(db, npi["ravi"], uuid.uuid4(), "x", "", "low", None, npi["ravi"].id)


# ---- update ----

def test_update_writes_one_entry_per_field_that_really_changed(db, npi):
    task_id = make(db, npi, due_at=date(2026, 10, 30))

    commands.update_task(db, npi["asha"], task_id, {"title": "Wire harness v2", "priority": "medium", "due_at": date(2026, 11, 2)})

    t = task(db, task_id)
    assert (t.title, t.priority, t.due_at) == ("Wire harness v2", "medium", date(2026, 11, 2))
    edits = {a.field: (a.old_value, a.new_value) for a in timeline(db, task_id) if a.kind == "edit"}
    assert edits == {"title": ("Wire harness", "Wire harness v2"), "due date": ("2026-10-30", "2026-11-02")}  # priority did not change


def test_update_with_nothing_new_adds_no_entry_and_null_clears_the_date(db, npi):
    task_id = make(db, npi, due_at=date(2026, 10, 30))

    commands.update_task(db, npi["asha"], task_id, {"title": "Wire harness"})
    assert kinds(db, task_id) == ["created"]
    commands.update_task(db, npi["asha"], task_id, {"due_at": None})

    assert task(db, task_id).due_at is None
    assert kinds(db, task_id) == ["created", "edit"]


def test_update_reassigns_by_name_and_refuses_a_stranger_or_a_done_task(db, npi):
    task_id = make(db, npi)

    commands.update_task(db, npi["asha"], task_id, {"assignee_id": npi["asha"].id})
    [entry] = [a for a in timeline(db, task_id) if a.kind == "reassign"]
    assert (entry.field, entry.old_value, entry.new_value) == ("assignee", "Ravi", "Asha")
    with refused("invalid_assignee"):
        commands.update_task(db, npi["asha"], task_id, {"assignee_id": npi["zoe"].id})
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)
    commands.move_task(db, npi["asha"], task_id, "done", "shipped")
    with refused("task_done"):
        commands.update_task(db, npi["asha"], task_id, {"assignee_id": npi["ravi"].id})


def test_a_rejected_update_changes_nothing(db, npi):
    task_id = make(db, npi)

    with refused("invalid_assignee"):
        commands.update_task(db, npi["asha"], task_id, {"title": "New title", "assignee_id": npi["zoe"].id})

    assert task(db, task_id).title == "Wire harness"


def test_only_the_teams_manager_can_update_move_or_delete_and_a_plain_member_cannot_comment(db, npi, admin):
    task_id = make(db, npi)

    for who in (admin, npi["ravi"]):
        with refused("forbidden"):
            commands.update_task(db, who, task_id, {"title": "x"})
        with refused("forbidden"):
            commands.delete_task(db, who, task_id)
        with refused("forbidden"):
            commands.move_task(db, who, task_id, "in_progress", None)
    with refused("forbidden"):
        commands.add_comment(db, npi["ravi"], task_id, uuid.uuid4(), "hello")
    assert kinds(db, task_id) == ["created"]
    assert task(db, task_id).title == "Wire harness"


def test_an_admin_and_the_teams_manager_may_both_comment(db, npi, admin):
    # Another team's manager is refused: see the "comment on a task" row of test_task_access.py.
    task_id = make(db, npi)
    commands.add_comment(db, admin, task_id, uuid.uuid4(), "looks good")
    commands.add_comment(db, npi["asha"], task_id, uuid.uuid4(), "thanks")

    comments = [a for a in timeline(db, task_id) if a.kind == "comment"]
    assert sorted((c.actor_id, c.note) for c in comments) == sorted([(admin.id, "looks good"), (npi["asha"].id, "thanks")])


# ---- delete ----

def test_delete_removes_the_task_and_its_timeline_while_to_do_or_in_progress(db, npi):
    for status in ("todo", "in_progress"):
        task_id = make(db, npi)
        if status == "in_progress":
            commands.move_task(db, npi["asha"], task_id, "in_progress", None)

        commands.delete_task(db, npi["asha"], task_id)

        assert task(db, task_id) is None
        assert timeline(db, task_id) == []


def audit_rows(db, action: str):
    db.expire_all()
    return db.query(AccessAuditLog).filter_by(action=action).order_by(AccessAuditLog.created_at).all()


def test_a_deleted_task_survives_in_the_append_only_audit_log_with_its_timeline(db, npi):
    task_id = make(db, npi, title="Wire harness", priority="high", due_at=date(2030, 1, 5))
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)

    commands.delete_task(db, npi["asha"], task_id)

    [entry] = audit_rows(db, "task.delete")
    assert (entry.actor_id, entry.team_id, entry.person_id) == (npi["asha"].id, uuid.UUID(npi["team"]["id"]), npi["ravi"].id)
    d = entry.details
    assert (d["task_id"], d["title"], d["status"], d["priority"], d["due_at"], d["assignee"]) == (
        str(task_id), "Wire harness", "in_progress", "high", "2030-01-05", "Ravi",
    )
    assert [t["kind"] for t in d["timeline"]] == ["created", "status"]  # what the deleted timeline held


def test_a_refused_delete_writes_no_audit_row(db, npi):
    task_id = make(db, npi)
    for to in ("in_progress", "done"):
        commands.move_task(db, npi["asha"], task_id, to, "ok")

    with refused("not_deletable"):
        commands.delete_task(db, npi["asha"], task_id)

    assert audit_rows(db, "task.delete") == []


def test_a_stranger_cannot_delete_and_leaves_no_audit_row(db, npi, admin):
    task_id = make(db, npi)

    with pytest.raises(AppError):
        commands.delete_task(db, npi["zoe"], task_id)

    assert audit_rows(db, "task.delete") == [] and task(db, task_id) is not None


def test_a_reassignment_is_written_to_the_audit_log_and_a_plain_edit_is_not(db, npi):
    task_id = make(db, npi, title="Wire harness")

    commands.update_task(db, npi["asha"], task_id, {"title": "Wire harness v2"})
    assert audit_rows(db, "task.reassign") == []

    commands.update_task(db, npi["asha"], task_id, {"assignee_id": npi["asha"].id})

    [entry] = audit_rows(db, "task.reassign")
    assert (entry.actor_id, entry.person_id) == (npi["asha"].id, npi["asha"].id)
    assert entry.details["from"] == "Ravi" and entry.details["to"] == "Asha" and entry.details["title"] == "Wire harness v2"


@pytest.mark.parametrize("path", [["in_progress", "blocked"], ["in_progress", "review"], ["in_progress", "done"]])
def test_delete_is_refused_once_blocked_in_review_or_done(db, npi, path):
    task_id = make(db, npi)
    for to in path:
        commands.move_task(db, npi["asha"], task_id, to, "because")

    with refused("not_deletable"):
        commands.delete_task(db, npi["asha"], task_id)

    assert task(db, task_id) is not None


# ---- move ----

def test_a_plain_start_needs_no_reason_and_is_logged_with_its_actor(db, npi):
    task_id = make(db, npi)

    commands.move_task(db, npi["asha"], task_id, "in_progress", None)

    [entry] = [a for a in timeline(db, task_id) if a.kind == "status"]
    assert (entry.old_value, entry.new_value, entry.note, entry.actor_id) == ("todo", "in_progress", None, npi["asha"].id)


@pytest.mark.parametrize("to", ["blocked", "todo", "done"])
def test_blocking_moving_back_and_finishing_need_a_reason(db, npi, to):
    task_id = make(db, npi)
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)

    with refused("reason_required"):
        commands.move_task(db, npi["asha"], task_id, to, "   ")
    commands.move_task(db, npi["asha"], task_id, to, "  because  ")

    assert task(db, task_id).status == to
    assert "because" in {a.note for a in timeline(db, task_id)}  # stored trimmed


def test_done_stamps_closed_at_and_reopening_clears_it(db, npi):
    task_id = make(db, npi)
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)

    commands.move_task(db, npi["asha"], task_id, "done", "shipped")
    assert task(db, task_id).closed_at is not None
    commands.move_task(db, npi["asha"], task_id, "in_progress", "found a defect")

    assert task(db, task_id).closed_at is None


def test_done_can_name_an_earlier_completion_day_and_the_timeline_says_so(db, npi):
    task_id = make(db, npi, due_at=date.today() + timedelta(days=1))
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)
    later = date.today() + timedelta(days=3)  # the server's "today" three days on; the task was created today

    commands.move_task(db, npi["asha"], task_id, "done", "shipped", completed_on=date.today() + timedelta(days=1), today=later)

    saved = task(db, task_id)
    assert saved.closed_at.astimezone().date() == date.today() + timedelta(days=1)
    assert saved.due_at == date.today() + timedelta(days=1)  # untouched
    assert any(a.note and a.note.endswith(f"(Completed on {saved.due_at.isoformat()})") for a in timeline(db, task_id))


def test_completion_day_runs_from_a_passed_due_date_to_today(db, npi):
    due = date.today() + timedelta(days=1)
    task_id = make(db, npi, due_at=due)
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)
    server_today = date.today() + timedelta(days=3)  # the due date has passed

    for outside in (server_today + timedelta(days=1), due - timedelta(days=1)):
        with refused("completed_on_invalid"):
            commands.move_task(db, npi["asha"], task_id, "done", "shipped", completed_on=outside, today=server_today)
    assert task(db, task_id).status == "in_progress"

    commands.move_task(db, npi["asha"], task_id, "done", "shipped", completed_on=due, today=server_today)

    assert task(db, task_id).closed_at.astimezone().date() == due


def test_completion_day_has_no_earliest_day_while_the_due_date_is_ahead_or_missing(db, npi):
    ahead = make(db, npi, due_at=date.today() + timedelta(days=5))
    none = make(db, npi)

    for task_id in (ahead, none):
        commands.move_task(db, npi["asha"], task_id, "in_progress", None)
        commands.move_task(db, npi["asha"], task_id, "done", "shipped", completed_on=date.today() - timedelta(days=2))

        assert task(db, task_id).closed_at.astimezone().date() == date.today() - timedelta(days=2)


def test_completion_day_is_only_for_done(db, npi):
    task_id = make(db, npi)

    with refused("completed_on_not_done"):
        commands.move_task(db, npi["asha"], task_id, "in_progress", None, completed_on=date.today())


def test_send_back_counts_but_other_backward_moves_do_not(db, npi):
    task_id = make(db, npi)
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)
    commands.move_task(db, npi["asha"], task_id, "review", None)

    commands.move_task(db, npi["asha"], task_id, "in_progress", "needs rework")
    assert task(db, task_id).returned_count == 1
    commands.move_task(db, npi["asha"], task_id, "todo", "paused")

    assert task(db, task_id).returned_count == 1


def test_a_move_the_rules_do_not_list_is_refused_and_changes_nothing(db, npi):
    task_id = make(db, npi)

    with refused("invalid_transition"):
        commands.move_task(db, npi["asha"], task_id, "done", "skipping ahead")

    assert task(db, task_id).status == "todo"
    assert kinds(db, task_id) == ["created"]


# ---- comments ----

def test_a_comment_is_a_timeline_entry_with_the_callers_id(db, npi):
    task_id, entry_id = make(db, npi), uuid.uuid4()

    commands.add_comment(db, npi["asha"], task_id, entry_id, "  Parts arrive Monday  ")

    entry = db.get(TaskActivity, entry_id)
    assert (entry.kind, entry.note, entry.actor_id, entry.source) == ("comment", "Parts arrive Monday", npi["asha"].id, "workboard")


def test_no_comment_on_a_done_task_or_a_blank_one(db, npi):
    task_id = make(db, npi)
    with refused("comment_required"):
        commands.add_comment(db, npi["asha"], task_id, uuid.uuid4(), "   ")
    commands.move_task(db, npi["asha"], task_id, "in_progress", None)
    commands.move_task(db, npi["asha"], task_id, "done", "shipped")

    with refused("task_done"):
        commands.add_comment(db, npi["asha"], task_id, uuid.uuid4(), "late thought")


def test_an_unknown_task_is_404_everywhere(db, npi):
    missing = uuid.uuid4()
    for call in (
        lambda: commands.update_task(db, npi["asha"], missing, {"title": "x"}),
        lambda: commands.delete_task(db, npi["asha"], missing),
        lambda: commands.move_task(db, npi["asha"], missing, "in_progress", None),
        lambda: commands.add_comment(db, npi["asha"], missing, uuid.uuid4(), "hi"),
    ):
        with refused("task_not_found"):
            call()
