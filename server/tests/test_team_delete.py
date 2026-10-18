from sqlalchemy import select

from models import AccessAuditLog, Task, Team
from tests.conftest import make_team


def delete(directory, who, team, **body):
    body.setdefault("confirm_name", team["name"])
    body.setdefault("reason", "wound up")
    return directory.call(who, "DELETE", f"/teams/{team['id']}", json=body)


def test_deleting_a_team_releases_everyone_and_revokes_the_managers_access(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    assert directory.call(asha, "GET", "/me").status_code == 200

    assert delete(directory, admin, team).status_code == 204

    assert db.scalar(select(Team).where(Team.name == "NPI")) is None
    for person in (asha, ravi):
        db.refresh(person)
        assert person.team_id is None
    assert asha.role == "member"
    # Asha is no longer a manager or admin, so she cannot sign in; both are back in the picker.
    assert directory.call(asha, "GET", "/me").json()["detail"]["code"] == "not_onboarded"
    assert directory.call(admin, "GET", "/teams").json() == []


def test_deleting_a_team_keeps_one_audit_snapshot_per_task(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    for title in ("Wire harness", "Test rig"):
        db.add(Task(team_id=team["id"], title=title, creator_id=asha.id, assignee_id=ravi.id))
    db.commit()

    assert delete(directory, admin, team).status_code == 204

    db.expire_all()
    entries = db.scalars(select(AccessAuditLog).where(AccessAuditLog.action == "task.delete")).all()
    assert sorted(e.details["title"] for e in entries) == ["Test rig", "Wire harness"]
    assert {e.reason for e in entries} == {"wound up"}
    assert {e.details["assignee"] for e in entries} == {"Ravi"}


def test_an_admin_who_ran_the_team_keeps_admin_access(directory, admin, db):
    helper = directory.person("Helper", admin=True)
    team = make_team(directory, admin, "NPI", helper)

    assert delete(directory, admin, team).status_code == 204

    db.refresh(helper)
    assert helper.role == "member" and helper.is_admin is True
    assert directory.call(helper, "GET", "/me").status_code == 200


def test_only_an_admin_can_delete_a_team(directory, admin, db):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    res = delete(directory, asha, team)
    assert res.status_code == 403
    assert db.scalar(select(Team).where(Team.name == "NPI")) is not None


def test_a_wrong_name_or_missing_reason_stops_the_delete(directory, admin, db):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))

    wrong = delete(directory, admin, team, confirm_name="QA")
    assert wrong.status_code == 422 and wrong.json()["detail"]["code"] == "confirmation_mismatch"
    blank = delete(directory, admin, team, reason=" ")
    assert blank.status_code == 422 and blank.json()["detail"]["code"] == "reason_required"
    assert db.scalar(select(Team).where(Team.name == "NPI")) is not None


def test_the_name_check_ignores_case_and_spaces(directory, admin):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))
    assert delete(directory, admin, team, confirm_name="  npi ").status_code == 204


def test_the_audit_log_keeps_a_record_of_the_deletion(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    delete(directory, admin, team)

    entry = db.scalar(select(AccessAuditLog).where(AccessAuditLog.action == "team.delete"))
    assert entry.reason == "wound up"
    assert entry.details["name"] == "NPI"
    assert entry.details["manager_id"] == str(asha.id)
    assert sorted(entry.details["member_ids"]) == sorted([str(asha.id), str(ravi.id)])
    # The earlier rows survive too: the team's history is not erased with the team.
    logged = directory.call(admin, "GET", "/audit-log").json()["items"]
    assert {e["action"] for e in logged} >= {"team.create", "team.delete"}


def test_deleting_an_unknown_team_is_a_404(directory, admin):
    ghost = {"id": "00000000-0000-0000-0000-000000000000", "name": "Ghost"}
    assert delete(directory, admin, ghost).status_code == 404
