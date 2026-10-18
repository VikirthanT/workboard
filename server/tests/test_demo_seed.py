"""seed/demo_db.py: the development demo world (Admin, Manager 1, Manager 2, two teams, 14 tasks). It must give a
usable board, load once, never touch real people, and refuse to run outside development."""
import importlib.util
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from core.config import settings
from identity import states
from models import Person, Task, TaskActivity, Team
from tests.conftest import make_team

# seed/demo_db.py is a script, not a package, so load it from its path.
_path = Path(__file__).resolve().parents[2] / "seed" / "demo_db.py"
_spec = importlib.util.spec_from_file_location("demo_db", _path)
demo_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_db)

TODAY = date(2026, 10, 17)


@pytest.fixture
def demo(db):
    message = demo_db.load_demo(db, TODAY)
    assert message.startswith("Demo data loaded"), message
    db.expire_all()
    return db


def person(db, email):
    return db.scalar(select(Person).where(Person.email == email))


def as_user(directory, email):
    """The dev sign-in names the caller by this address, so use the real one."""
    return type("Caller", (), {"email": email})()


# ---- what gets loaded ----

def test_the_three_accounts_can_sign_in_and_nobody_else_in_the_demo_can(directory, demo):
    for email, admin in (("admin@atimotors.com", True), ("manager1@atimotors.com", False), ("manager2@atimotors.com", False)):
        res = directory.call(as_user(directory, email), "GET", "/me")
        assert res.status_code == 200, email
        assert res.json()["is_admin"] is admin
    members = directory.call(as_user(directory, "demo.aarav@atimotors.com"), "GET", "/me")
    assert (members.status_code, members.json()["detail"]["code"]) == (403, "not_onboarded")


def test_the_login_list_offers_the_demo_accounts(directory, demo):
    listed = {a["name"]: a["can_sign_in"] for a in directory.call(None, "GET", "/dev/accounts").json()}

    assert listed["Admin"] and listed["Manager 1"] and listed["Manager 2"]
    assert list(listed.values()).count(False) == 2  # two plain members shown as refused


def test_two_teams_with_their_managers_and_people(demo):
    npi, val = (demo.scalar(select(Team).where(Team.name == name)) for name in ("NPI", "Validation"))

    assert npi.manager.name == "Manager 1" and val.manager.name == "Manager 2"
    assert sorted(p.name for p in demo.scalars(select(Person).where(Person.team_id == npi.id)).unique() if p.role == "member") == [
        "Aarav Menon", "Meera Pillai", "Rohan Shetty", "Sana Qureshi"]
    assert person(demo, "demo.sana@atimotors.com").active is False  # left; her open task needs a new owner


def test_fourteen_tasks_in_every_state(demo):
    by_status = Counter(status for (status,) in demo.execute(select(Task.status)))

    assert by_status == {"todo": 2, "in_progress": 4, "blocked": 2, "review": 4, "done": 2}


def test_the_timelines_are_back_dated_and_in_order(demo):
    t1 = demo.scalar(select(Task).where(Task.title.like("Migrate telemetry%")))
    timeline = list(demo.scalars(select(TaskActivity).where(TaskActivity.task_id == t1.id).order_by(TaskActivity.created_at)))

    assert [e.kind for e in timeline] == ["created", "status", "comment", "status"]
    assert [e.new_value for e in timeline if e.kind == "status"] == ["in_progress", "review"]
    assert timeline[0].created_at.date() == date(2026, 10, 8)  # created nine days before TODAY
    assert t1.updated_at == timeline[-1].created_at


def test_send_backs_and_close_times_follow_the_steps(demo):
    firmware = demo.scalar(select(Task).where(Task.title.like("Add retry%")))
    node = demo.scalar(select(Task).where(Task.title.like("Upgrade build image%")))
    open_task = demo.scalar(select(Task).where(Task.title.like("Document the release%")))

    assert firmware.returned_count == 1 and firmware.status == "review"
    assert node.status == "done" and node.closed_at.date() == date(2026, 10, 5)
    assert open_task.closed_at is None


def test_every_task_has_a_creator_an_owner_and_a_team_that_matches(demo):
    for task in demo.scalars(select(Task)):
        owner, creator = demo.get(Person, task.assignee_id), demo.get(Person, task.creator_id)
        assert owner.team_id == task.team_id and creator.role == "manager" and creator.team_id == task.team_id


def test_teams_were_made_through_the_real_services_so_the_audit_log_has_them(demo):
    from models import AccessAuditLog

    actions = Counter(a for (a,) in demo.execute(select(AccessAuditLog.action)))

    assert actions["team.create"] == 2 and actions["member.add"] == 6


# ---- the board it gives ----

def test_manager_one_sees_a_realistic_board(directory, demo):
    manager = as_user(directory, "manager1@atimotors.com")

    board = directory.call(manager, "GET", "/board").json()

    assert board["team"]["name"] == "NPI" and board["read_only"] is False
    assert len(board["tasks"]) == 9
    assert [t["title"] for t in board["orphans"]] == ["Compile field-test feedback"]
    blocked = next(t for t in board["tasks"] if t["title"].startswith("Fix flaky"))
    assert blocked["latest_reason"]["kind"] == "blocked" and blocked["overdue"] is True or blocked["status"] == "blocked"
    assert sum(t["status"] == "review" for t in board["tasks"]) == 2  # the header's "needs review" count


def test_the_admin_can_read_both_boards_but_not_act(directory, demo):
    admin = as_user(directory, "admin@atimotors.com")
    team = demo.scalar(select(Team).where(Team.name == "Validation"))

    board = directory.call(admin, "GET", f"/board?team={team.id}").json()

    assert board["read_only"] is True and len(board["tasks"]) == 5
    assert all(not t["actions"]["can_edit"] for t in board["tasks"])


# ---- safety ----

def test_loading_twice_changes_nothing(demo):
    people, tasks = demo.scalar(select(func.count(Person.id))), demo.scalar(select(func.count(Task.id)))

    message = demo_db.load_demo(demo, TODAY)

    assert "already loaded" in message
    assert (demo.scalar(select(func.count(Person.id))), demo.scalar(select(func.count(Task.id)))) == (people, tasks)


def test_it_does_not_load_over_a_team_or_an_address_that_already_exists(db, directory, admin):
    existing = directory.person("Asha")
    make_team(directory, admin, "NPI", existing)
    db.expire_all()

    message = demo_db.load_demo(db, TODAY)

    assert message.startswith("Demo data not loaded") and "NPI" in message
    assert db.scalar(select(func.count(Person.id)).where(Person.slack_user_id.like("DEMO-%"))) == 0
    assert db.scalar(select(func.count(Task.id))) == 0


def test_reset_removes_only_the_demo_and_loads_it_again(db, directory, demo):
    boss, asha = directory.person("Boss", admin=True), directory.person("Asha")  # not the demo's admin@ address
    make_team(directory, boss, "QA", asha)
    db.expire_all()

    demo_db.reset_demo(db)

    assert db.scalar(select(func.count(Person.id)).where(Person.slack_user_id.like("DEMO-%"))) == 0
    assert db.scalar(select(func.count(Task.id))) == 0
    assert db.scalar(select(Team.name).where(Team.name == "QA")) == "QA"  # a real team is untouched
    assert person(db, "asha@atimotors.com") is not None
    assert demo_db.load_demo(db, TODAY).startswith("Demo data loaded")


def test_remove_takes_the_demo_away_and_leaves_everything_else_including_the_audit_log(db, directory, demo):
    from models import AccessAuditLog

    boss, asha = directory.person("Boss", admin=True), directory.person("Asha")
    make_team(directory, boss, "QA", asha)
    db.expire_all()
    audit_rows = db.scalar(select(func.count(AccessAuditLog.id)))

    assert demo_db.main(["--remove"]) == 0

    db.expire_all()
    assert db.scalar(select(func.count(Person.id)).where(Person.slack_user_id.like("DEMO-%"))) == 0
    assert db.scalar(select(func.count(Task.id))) == 0 and db.scalar(select(func.count(TaskActivity.id))) == 0
    assert db.scalar(select(Team.name).where(Team.name == "QA")) == "QA" and person(db, "asha@atimotors.com") is not None
    assert db.scalar(select(func.count(AccessAuditLog.id))) == audit_rows  # append-only: the demo's entries stay


def test_the_directory_load_never_deactivates_the_demo_accounts(demo):
    import importlib.util as util

    spec = util.spec_from_file_location("load_db", Path(__file__).resolve().parents[2] / "seed" / "load_db.py")
    load_db = util.module_from_spec(spec)
    spec.loader.exec_module(load_db)

    left = load_db.deactivate_missing(demo, {"SOMEONE-ELSE"})  # a file that contains none of the demo people

    assert not [p for p in left if p.slack_user_id.startswith(states.DEMO_SLACK_PREFIX)]
    assert person(demo, "manager1@atimotors.com").active is True


def test_it_refuses_to_run_when_dev_auth_is_off(monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)

    with pytest.raises(SystemExit, match="development only"):
        demo_db.main([])
