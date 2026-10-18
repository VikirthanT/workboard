"""Who may call each task endpoint, every kind of caller against every endpoint (the tasks counterpart of
test_access_matrix.py). The point is the refusals: another team's manager, an admin who only reads, a person who
cannot sign in, and nobody at all must each be turned away, and the owner must get through."""
import json

import pytest

from tests.conftest import make_team

ACTORS = ["anon", "plain_member", "other_manager", "own_manager", "admin"]


@pytest.fixture
def world(db, directory, admin, npi):
    """NPI: Asha (manager) and Ravi (plain member, cannot sign in), with one task. QA: Omar (another manager)."""
    omar = directory.person("Omar")
    make_team(directory, admin, "QA", omar)
    res = directory.call(npi["asha"], "POST", "/tasks", json={"title": "Wire harness", "assignee_id": str(npi["ravi"].id)})
    assert res.status_code == 201, res.text
    db.expire_all()
    return {
        "actors": {"anon": None, "plain_member": npi["ravi"], "other_manager": omar, "own_manager": npi["asha"], "admin": admin},
        "task": res.json()["id"],
    }


# (label, method, path with {task}, body, expected status per actor)
CASES = [
    ("read a task", "GET", "/tasks/{task}", None,
     dict(anon=401, plain_member=403, other_manager=403, own_manager=200, admin=200)),
    ("edit a task", "PATCH", "/tasks/{task}", {"title": "New title"},
     dict(anon=401, plain_member=403, other_manager=403, own_manager=200, admin=403)),
    ("move a task", "POST", "/tasks/{task}/status", {"to": "in_progress"},
     dict(anon=401, plain_member=403, other_manager=403, own_manager=200, admin=403)),
    ("comment on a task", "POST", "/tasks/{task}/comments", {"body": "Parts arrive Monday"},
     dict(anon=401, plain_member=403, other_manager=403, own_manager=201, admin=201)),  # an admin may comment on any board
    ("delete a task", "DELETE", "/tasks/{task}", None,
     dict(anon=401, plain_member=403, other_manager=403, own_manager=204, admin=403)),
]


@pytest.mark.parametrize("actor", ACTORS)
@pytest.mark.parametrize("label,method,path,body,expected", CASES, ids=[case[0] for case in CASES])
def test_who_may_call_what(directory, world, label, method, path, body, expected, actor):
    kwargs = {"json": body} if body is not None else {}

    res = directory.call(world["actors"][actor], method, path.format(task=world["task"]), **kwargs)

    assert res.status_code == expected[actor], f"{label} as {actor}: {res.status_code} {res.text}"


def test_only_the_teams_manager_can_create_a_task(directory, admin, npi, world):
    body = {"title": "New", "assignee_id": str(npi["ravi"].id)}

    admin_res = directory.call(admin, "POST", "/tasks", json=body)  # an admin on no team has nowhere to put it
    plain_res = directory.call(npi["ravi"], "POST", "/tasks", json=body)
    anon_res = directory.call(None, "POST", "/tasks", json=body)
    own_res = directory.call(npi["asha"], "POST", "/tasks", json=body)

    assert (admin_res.status_code, plain_res.status_code, anon_res.status_code, own_res.status_code) == (403, 403, 401, 201)


def test_another_teams_manager_cannot_put_a_task_on_this_team_by_naming_its_id(directory, npi, world, db):
    omar = world["actors"]["other_manager"]
    body = {"title": "Sneaky", "assignee_id": str(npi["ravi"].id), "team_id": npi["team"]["id"]}

    res = directory.call(omar, "POST", "/tasks", json=body)

    # Omar's task would land on his own team, so Ravi (NPI) is not a valid assignee; `team_id` is not even a field.
    assert (res.status_code, res.json()["detail"]["code"]) == (422, "invalid_assignee")


def test_a_manager_cannot_reassign_a_task_to_someone_on_another_team(directory, npi, world):
    omar = world["actors"]["other_manager"]

    res = directory.call(npi["asha"], "PATCH", f"/tasks/{world['task']}", json={"assignee_id": str(omar.id)})

    assert (res.status_code, res.json()["detail"]["code"]) == (422, "invalid_assignee")


def test_the_board_and_report_follow_the_same_team_rules(directory, admin, npi, world):
    omar = world["actors"]["other_manager"]
    today = "2026-10-17"
    for path in (f"/board?team={npi['team']['id']}", f"/reports/team?from={today}&to={today}&team={npi['team']['id']}"):
        assert directory.call(None, "GET", path).status_code == 401
        assert directory.call(npi["ravi"], "GET", path).status_code == 403  # cannot sign in
        assert directory.call(omar, "GET", path).status_code == 403  # another team's manager
        assert directory.call(npi["asha"], "GET", path).status_code == 200
        assert directory.call(admin, "GET", path).status_code == 200
