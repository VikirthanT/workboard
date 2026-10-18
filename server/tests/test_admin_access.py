import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from models import AccessAuditLog
from tests.conftest import make_team


def set_admin(directory, who, person, is_admin: bool, reason: str = "needs the panel"):
    return directory.call(who, "PATCH", f"/people/{person.id}/admin", json={"is_admin": is_admin, "reason": reason})


def test_a_team_member_made_admin_can_sign_in_and_keeps_their_team(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    assert directory.call(ravi, "GET", "/me").json()["detail"]["code"] == "not_onboarded"

    res = set_admin(directory, admin, ravi, True)

    assert res.status_code == 200
    assert res.json()["is_admin"] is True
    assert res.json()["role"] == "member" and res.json()["team_name"] == "NPI"
    assert directory.call(ravi, "GET", "/me").status_code == 200


def test_a_manager_made_admin_keeps_running_the_team(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    make_team(directory, admin, "QA", ravi)
    assert [t["name"] for t in directory.call(asha, "GET", "/teams").json()] == ["NPI"]

    res = set_admin(directory, admin, asha, True)

    assert res.json()["role"] == "manager" and res.json()["is_admin"] is True
    # Now an admin, Asha sees every team; she still runs NPI.
    teams = directory.call(asha, "GET", "/teams").json()
    assert [t["name"] for t in teams] == ["NPI", "QA"]
    assert teams[0]["manager"]["id"] == str(asha.id)


def test_revoking_admin_from_a_plain_member_closes_the_door(directory, admin):
    ravi = directory.person("Ravi", admin=True)
    assert directory.call(ravi, "GET", "/me").status_code == 200

    assert set_admin(directory, admin, ravi, False).status_code == 200
    assert directory.call(ravi, "GET", "/me").json()["detail"]["code"] == "not_onboarded"


def test_only_an_admin_can_change_admin_rights(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)

    res = set_admin(directory, asha, ravi, True)
    assert res.status_code == 403 and res.json()["detail"]["code"] == "forbidden"


def test_a_reason_is_required(directory, admin):
    ravi = directory.person("Ravi")
    res = set_admin(directory, admin, ravi, True, reason="  ")
    assert res.status_code == 422 and res.json()["detail"]["code"] == "reason_required"


def test_setting_the_state_a_person_already_has_is_refused(directory, admin):
    ravi = directory.person("Ravi")
    assert set_admin(directory, admin, ravi, False).json()["detail"]["code"] == "admin_unchanged"
    set_admin(directory, admin, ravi, True)
    assert set_admin(directory, admin, ravi, True).json()["detail"]["code"] == "admin_unchanged"


def test_the_last_admin_cannot_be_revoked_but_one_of_two_can(directory, admin):
    res = set_admin(directory, admin, admin, False)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "last_admin"

    second = directory.person("Second", admin=True)
    assert set_admin(directory, admin, second, False).status_code == 200
    # Back to one admin: the same refusal applies again.
    assert set_admin(directory, admin, admin, False).json()["detail"]["code"] == "last_admin"


def test_an_inactive_person_cannot_be_made_admin(directory, admin, db):
    ravi = directory.person("Ravi")
    ravi.active = False
    db.commit()
    res = set_admin(directory, admin, ravi, True)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "person_inactive"


def test_grant_and_revoke_are_audited(directory, admin, db):
    ravi = directory.person("Ravi")
    set_admin(directory, admin, ravi, True, reason="builds dashboards")
    set_admin(directory, admin, ravi, False, reason="moved on")

    rows = db.scalars(select(AccessAuditLog).where(AccessAuditLog.person_id == ravi.id).order_by(AccessAuditLog.created_at)).all()
    assert [(r.action, r.reason, r.actor_id) for r in rows] == [
        ("admin.grant", "builds dashboards", admin.id),
        ("admin.revoke", "moved on", admin.id),
    ]


def test_the_audit_log_cannot_be_changed_even_with_raw_sql(db):
    db.execute(text("INSERT INTO access_audit_log (action) VALUES ('probe')"))
    db.commit()
    for statement in ("UPDATE access_audit_log SET action = 'x'", "DELETE FROM access_audit_log"):
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text(statement))
        db.rollback()
