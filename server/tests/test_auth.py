from core.config import settings
from tests.conftest import make_team


def test_no_header_is_unauthenticated(directory):
    assert directory.call(None, "GET", "/me").status_code == 401


def test_plain_member_cannot_sign_in(directory):
    member = directory.person("Meena")
    res = directory.call(member, "GET", "/me")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "not_onboarded"


def test_unknown_and_foreign_accounts_are_refused(directory, client):
    unknown = client.get("/api/me", headers={"X-Dev-User-Email": "ghost@atimotors.com"})
    assert unknown.json()["detail"]["code"] == "not_onboarded"
    foreign = client.get("/api/me", headers={"X-Dev-User-Email": "someone@gmail.com"})
    assert foreign.json()["detail"]["code"] == "domain_not_allowed"


def test_manager_and_admin_can_sign_in(directory, admin):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    assert directory.call(asha, "GET", "/me").json()["team_name"] == "NPI"
    assert directory.call(admin, "GET", "/me").status_code == 200


def test_manager_cannot_create_teams_or_read_the_audit_log(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    create = directory.call(
        asha, "POST", "/teams", json={"name": "QA", "initial_manager_person_id": str(ravi.id), "reason": "x"}
    )
    assert create.status_code == 403
    assert directory.call(asha, "GET", "/audit-log").status_code == 403


def test_deactivated_manager_cannot_sign_in(directory, admin, db):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    asha.active = False
    db.commit()
    assert directory.call(asha, "GET", "/me").status_code == 403


def test_without_dev_auth_every_protected_route_is_closed(directory, admin, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)
    res = directory.call(admin, "GET", "/me")
    assert res.status_code == 501
    assert res.json()["detail"]["code"] == "auth_not_configured"
