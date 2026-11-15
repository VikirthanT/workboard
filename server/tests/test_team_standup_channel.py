"""A team's standup channel: which standup its suggestions are read from. Admins set it; every change is audited."""
import uuid

from sqlalchemy import select

from models import AccessAuditLog
from tests.conftest import make_team


def create(directory, admin, name, manager, **extra):
    return directory.call(
        admin, "POST", "/teams",
        json={"name": name, "initial_manager_person_id": str(manager.id), "reason": "set up", **extra},
    )


def set_channel(directory, who, team, channel, reason="moved"):
    return directory.call(
        who, "PATCH", f"/teams/{team['id']}/standup-channel", json={"standup_channel_id": channel, "reason": reason}
    )


def test_a_team_needs_a_standup_channel_when_it_is_created(directory, admin):
    ok = create(directory, admin, "NPI", directory.person("Asha"), standup_channel_id=" C0NPI ")
    missing = create(directory, admin, "QA", directory.person("Ravi"))
    blank = create(directory, admin, "Mech", directory.person("Meena"), standup_channel_id="  ")
    spaced = create(directory, admin, "Val", directory.person("Zoe"), standup_channel_id="C0 VAL")

    assert ok.status_code == 201 and ok.json()["standup_channel_id"] == "C0NPI"  # trimmed
    assert missing.status_code == 422
    assert (blank.status_code, blank.json()["detail"]["code"]) == (422, "channel_required")
    assert (spaced.status_code, spaced.json()["detail"]["code"]) == (422, "invalid_channel")
    assert [t["name"] for t in directory.call(admin, "GET", "/teams").json()] == ["NPI"]  # the refused ones made no team


def test_an_admin_sets_changes_and_clears_the_channel_and_each_change_is_audited(directory, admin, db):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))

    assert set_channel(directory, admin, team, "C0ONE", "first").json()["standup_channel_id"] == "C0ONE"
    assert set_channel(directory, admin, team, "C0TWO", "renamed").json()["standup_channel_id"] == "C0TWO"
    assert set_channel(directory, admin, team, None, "no standup").json()["standup_channel_id"] is None
    listed = directory.call(admin, "GET", "/teams").json()
    assert listed[0]["standup_channel_id"] is None

    entries = db.scalars(
        select(AccessAuditLog).where(AccessAuditLog.action == "team.standup_channel_change").order_by(AccessAuditLog.created_at)
    ).all()
    assert [(e.details["old_channel_id"], e.details["new_channel_id"], e.reason) for e in entries] == [
        ("C0TEST", "C0ONE", "first"),  # make_team starts every team on C0TEST
        ("C0ONE", "C0TWO", "renamed"),
        ("C0TWO", None, "no standup"),
    ]


def test_a_manager_sets_their_own_teams_channel_without_a_reason_but_not_another_teams(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    other = make_team(directory, admin, "Validation", ravi)

    refused = set_channel(directory, asha, other, "C0NPI")
    res = set_channel(directory, asha, team, "C0NPI", reason=None)

    assert refused.status_code == 403
    assert res.status_code == 200
    assert res.json()["standup_channel_id"] == "C0NPI"


def test_the_rules_around_a_change(directory, admin):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))
    set_channel(directory, admin, team, "C0NPI")

    same = set_channel(directory, admin, team, "C0NPI")
    no_reason = set_channel(directory, admin, team, "C0NEW", reason="  ")
    spaced = set_channel(directory, admin, team, "C0 NEW")
    unknown = set_channel(directory, admin, {"id": str(uuid.uuid4())}, "C0NEW")

    assert (same.status_code, same.json()["detail"]["code"]) == (409, "same_channel")
    assert (no_reason.status_code, no_reason.json()["detail"]["code"]) == (422, "reason_required")
    assert (spaced.status_code, spaced.json()["detail"]["code"]) == (422, "invalid_channel")
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (404, "team_not_found")
    assert directory.call(admin, "GET", "/teams").json()[0]["standup_channel_id"] == "C0NPI"
