"""A person who is both admin and manager: full rights on the team they run, and on every other team's board only
what any admin has (read, and comment on a task that is not Done). Admin never widens what a manager may do to tasks."""
import pytest

from tests.conftest import make_team


@pytest.fixture
def world(db, directory):
    """Asha is an admin and runs NPI (Ravi is a member). Omar runs QA, which has one task."""
    boss = directory.person("Admin", admin=True)
    asha = directory.person("Asha", admin=True)
    ravi, omar, lena = directory.person("Ravi"), directory.person("Omar"), directory.person("Lena")
    npi = make_team(directory, boss, "NPI", asha)
    qa = make_team(directory, boss, "QA", omar)
    directory.call(asha, "POST", f"/teams/{npi['id']}/members", json={"person_id": str(ravi.id), "reason": "joins"})
    directory.call(omar, "POST", f"/teams/{qa['id']}/members", json={"person_id": str(lena.id)})
    theirs = directory.call(omar, "POST", "/tasks", json={"title": "QA task", "assignee_id": str(lena.id)}).json()
    db.expire_all()
    return {"asha": asha, "ravi": ravi, "lena": lena, "npi": npi, "qa": qa, "theirs": theirs, "boss": boss}


def test_on_their_own_team_they_act_fully(directory, world):
    asha, ravi = world["asha"], world["ravi"]
    made = directory.call(asha, "POST", "/tasks", json={"title": "Mine", "assignee_id": str(ravi.id)})
    assert made.status_code == 201 and made.json()["team_id"] == world["npi"]["id"]
    tid = made.json()["id"]

    assert directory.call(asha, "PATCH", f"/tasks/{tid}", json={"title": "Renamed"}).status_code == 200
    assert directory.call(asha, "POST", f"/tasks/{tid}/status", json={"to": "in_progress"}).status_code == 200
    board = directory.call(asha, "GET", "/board").json()
    assert board["team"]["id"] == world["npi"]["id"] and board["read_only"] is False
    assert directory.call(asha, "POST", f"/tasks/{tid}/status", json={"to": "todo", "note": "back"}).status_code == 200
    assert directory.call(asha, "DELETE", f"/tasks/{tid}").status_code == 204


def test_on_another_team_they_read_and_comment_but_change_nothing(directory, world):
    asha, tid = world["asha"], world["theirs"]["id"]

    assert directory.call(asha, "GET", f"/tasks/{tid}").status_code == 200
    assert directory.call(asha, "POST", f"/tasks/{tid}/comments", json={"body": "Looks fine"}).status_code == 201
    for method, path, body in (
        ("PATCH", f"/tasks/{tid}", {"title": "Mine now"}),
        ("POST", f"/tasks/{tid}/status", {"to": "in_progress"}),
        ("DELETE", f"/tasks/{tid}", None),
    ):
        res = directory.call(asha, method, path, json=body)
        assert (res.status_code, res.json()["detail"]["code"]) == (403, "forbidden"), (method, path)

    other = directory.call(asha, "GET", f"/board?team={world['qa']['id']}").json()
    assert other["read_only"] is True
    [card] = other["tasks"]
    assert card["actions"] == {"can_edit": False, "can_delete": False, "can_change_assignee": False, "can_comment": True, "transitions": []}
    assert directory.call(world["boss"], "GET", f"/tasks/{tid}").json()["task"]["title"] == "QA task"  # nothing was changed


def test_a_new_task_always_lands_on_their_own_team_and_cannot_be_given_to_the_other_team(directory, world):
    res = directory.call(world["asha"], "POST", "/tasks", json={"title": "Cross", "assignee_id": str(world["lena"].id)})

    assert res.status_code == 422 and res.json()["detail"]["code"] == "invalid_assignee"


def test_as_an_admin_they_manage_people_on_any_team_and_the_reason_rule_follows_the_admin(directory, world):
    zoe = directory.person("Zoe")
    qa_id = world["qa"]["id"]

    assert directory.call(world["asha"], "POST", f"/teams/{qa_id}/members", json={"person_id": str(zoe.id)}).status_code == 201
    no_reason = directory.call(world["asha"], "DELETE", f"/teams/{qa_id}/members/{zoe.id}", json={"reason": "  "})
    assert (no_reason.status_code, no_reason.json()["detail"]["code"]) == (422, "reason_required")  # admin: a reason is required
    assert directory.call(world["asha"], "DELETE", f"/teams/{qa_id}/members/{zoe.id}", json={"reason": "wrong team"}).status_code == 204
