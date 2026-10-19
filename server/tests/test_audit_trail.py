"""The side effect of every identity change: exactly one audit row, with the right action, actor, person, team and
reason, and nothing at all for a change that was refused. Read back through GET /audit-log, so the names the screen
shows are checked too."""
from tests.conftest import make_team


def log(directory, admin):
    """Oldest first, as (action, actor, person, team, reason)."""
    items = directory.call(admin, "GET", "/audit-log?limit=200").json()["items"]
    return [(e["action"], e["actor_name"], e["person_name"], e["team_name"], e["reason"]) for e in reversed(items)]


def test_every_identity_change_leaves_one_matching_audit_row(directory, admin):
    asha, ravi, zoe = directory.person("Asha"), directory.person("Ravi"), directory.person("Zoe")
    team = make_team(directory, admin, "NPI", asha)
    tid = team["id"]
    directory.call(asha, "POST", f"/teams/{tid}/members", json={"person_id": str(ravi.id)})  # a manager need not say why
    directory.call(asha, "DELETE", f"/teams/{tid}/members/{ravi.id}", json={"reason": "  moved to QA  "})
    directory.call(admin, "POST", f"/teams/{tid}/members", json={"person_id": str(ravi.id), "reason": "back again"})
    directory.call(admin, "PATCH", f"/teams/{tid}/manager", json={"person_id": str(ravi.id), "reason": "Asha is leaving"})
    directory.call(admin, "PATCH", f"/people/{zoe.id}/admin", json={"is_admin": True, "reason": "covers leave"})
    directory.call(admin, "PATCH", f"/people/{zoe.id}/admin", json={"is_admin": False, "reason": "back from leave"})

    assert log(directory, admin) == [
        ("team.create", "Admin", "Asha", "NPI", "set up"),  # make_team's reason
        ("member.add", "Asha", "Ravi", "NPI", None),
        ("member.remove", "Asha", "Ravi", "NPI", "moved to QA"),  # trimmed
        ("member.add", "Admin", "Ravi", "NPI", "back again"),
        ("team.manager_change", "Admin", "Ravi", "NPI", "Asha is leaving"),
        ("admin.grant", "Admin", "Zoe", None, "covers leave"),
        ("admin.revoke", "Admin", "Zoe", None, "back from leave"),
    ]

    directory.call(admin, "DELETE", f"/teams/{tid}", json={"confirm_name": "NPI", "reason": "closed"})
    last = log(directory, admin)[-1]
    assert last == ("team.delete", "Admin", None, "NPI", "closed")  # the deleted team's name survives in the row


def test_a_refused_change_writes_no_audit_row(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    tid = make_team(directory, admin, "NPI", asha)["id"]
    directory.call(admin, "POST", f"/teams/{tid}/members", json={"person_id": str(ravi.id), "reason": "joins"})
    before = log(directory, admin)

    refused = [
        directory.call(admin, "POST", f"/teams/{tid}/members", json={"person_id": str(ravi.id), "reason": "twice"}),  # 409 already on a team
        directory.call(admin, "DELETE", f"/teams/{tid}/members/{asha.id}", json={"reason": "x"}),  # 409 the manager
        directory.call(admin, "DELETE", f"/teams/{tid}/members/{ravi.id}", json={"reason": "  "}),  # 422 admin needs a reason
        directory.call(admin, "PATCH", f"/teams/{tid}/manager", json={"person_id": str(asha.id), "reason": "same"}),  # 409 already manager
        directory.call(admin, "PATCH", f"/people/{admin.id}/admin", json={"is_admin": False, "reason": "only admin"}),  # 409 last admin
        directory.call(admin, "PATCH", f"/people/{ravi.id}/admin", json={"is_admin": False, "reason": "no-op"}),  # 409 unchanged
        directory.call(admin, "DELETE", f"/teams/{tid}", json={"confirm_name": "wrong", "reason": "x"}),  # 422 name mismatch
        directory.call(asha, "POST", f"/teams/{tid}/members", json={"person_id": str(directory.person("Zoe").id)}),  # allowed: control
    ]

    assert [r.status_code for r in refused[:-1]] == [409, 409, 422, 409, 409, 409, 422]
    assert refused[-1].status_code == 201
    assert log(directory, admin) == before + [("member.add", "Asha", "Zoe", "NPI", None)]  # only the allowed one is logged


def test_only_an_admin_can_read_the_log_and_it_has_no_write_route(directory, admin):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)

    assert directory.call(asha, "GET", "/audit-log").status_code == 403
    assert directory.call(None, "GET", "/audit-log").status_code == 401
    for method in ("POST", "PATCH", "PUT", "DELETE"):
        assert directory.call(admin, method, "/audit-log").status_code in (404, 405)
