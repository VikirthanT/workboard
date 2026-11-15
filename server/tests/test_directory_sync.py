"""The people directory kept in step with the Slack workspace: who is listed, the merge rules, the safety limits, the audit
entry of each run, the runner and the paged Slack call. Slack is faked at its edge; the people are made up."""
import pytest
from sqlalchemy import func, select

from core.config import settings
from core.exceptions import AppError
from identity.services import directory_sync
from models import AccessAuditLog, Person
from slack import client
from tests.conftest import make_team

DOMAIN = "atimotors.com"


def member(slack_id: str, email: str, name: str, **over) -> dict:
    """One entry of Slack's users.list answer."""
    return {"id": slack_id, "profile": {"email": email, "display_name": name}, **over}


def count(db, *where) -> int:
    return db.scalar(select(func.count()).select_from(Person).where(*where))


def audit(db, action):
    return list(db.scalars(select(AccessAuditLog).where(AccessAuditLog.action == action).order_by(AccessAuditLog.created_at)))


# ---- who is listed ----

def test_the_listed_people_come_from_the_workspace_with_their_names_and_lower_case_emails():
    members, notes = directory_sync.members_from_slack([
        member("U1", "  Asha@AtiMotors.com ", " Asha "),
        {"id": "U2", "real_name": "Ravi Kumar", "profile": {"email": "ravi@atimotors.com", "display_name": "", "real_name": "Ravi Kumar"}},
    ], DOMAIN)

    assert [(m.slack_user_id, m.email, m.name) for m in members] == [
        ("U1", "asha@atimotors.com", "Asha"), ("U2", "ravi@atimotors.com", "Ravi Kumar"),  # the full name when there is no display name
    ]
    assert notes == []


def test_bots_slackbot_deactivated_accounts_and_guests_are_left_out_without_a_note():
    members, notes = directory_sync.members_from_slack([
        member("U1", "asha@atimotors.com", "Asha"),
        member("UBOT", "bot@atimotors.com", "Some Bot", is_bot=True),
        member("USLACKBOT", "slackbot@atimotors.com", "Slackbot"),
        member("UGONE", "gone@atimotors.com", "Gone", deleted=True),
        member("UGUEST", "guest@atimotors.com", "Guest", is_restricted=True),
        member("USINGLE", "single@atimotors.com", "Single channel guest", is_ultra_restricted=True),
        {"id": "UAPP", "profile": {"email": "app@atimotors.com", "display_name": "An app", "bot_id": "B1"}},
    ], DOMAIN)

    assert [m.slack_user_id for m in members] == ["U1"]
    assert notes == []


def test_a_person_skipped_for_a_reason_worth_reading_is_noted():
    members, notes = directory_sync.members_from_slack([
        member("U1", "asha@atimotors.com", "Asha"),
        member("U2", "ravi@atimotors.com", ""),
        member("U3", "outsider@gmail.com", "Outsider"),
        member("U4", "asha@atimotors.com", "Asha again"),
        member("U1", "other@atimotors.com", "Same Slack id"),
        member("U5", "", "No email"),
    ], DOMAIN)

    assert [m.slack_user_id for m in members] == ["U1"]
    assert len(notes) == 5
    assert sum("missing" in n for n in notes) == 2 and any("not @atimotors.com" in n for n in notes) and sum("duplicate" in n for n in notes) == 2


# ---- the merge rules ----

def test_running_it_twice_adds_nobody_new_and_each_run_is_in_the_audit_log(db):
    slack = [member("U1", "asha@atimotors.com", "Asha"), member("U2", "ravi@atimotors.com", "Ravi")]

    directory_sync.sync_directory(db, slack)
    directory_sync.sync_directory(db, slack, reason="Run by hand")

    assert count(db) == 2
    first, second = audit(db, "directory.sync")
    assert (first.details["added"], second.details["added"]) == (2, 0)
    assert (first.reason, second.reason) == ("Weekly Slack sync", "Run by hand")
    assert first.actor_id is None  # the server's own run: no person
    assert directory_sync.last_run(db).id == second.id


def test_a_run_refreshes_name_and_email_but_never_role_team_or_admin(directory, admin, db):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    directory_sync.sync_directory(db, [member(asha.slack_user_id, "asha.k@atimotors.com", "Asha K"), member(admin.slack_user_id, admin.email, "Admin")])

    db.refresh(asha)
    assert (asha.name, asha.email) == ("Asha K", "asha.k@atimotors.com")
    assert asha.role == "manager" and str(asha.team_id) == team["id"]


def test_people_missing_from_slack_are_deactivated_not_deleted_and_admins_never(directory, db):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    boss = directory.person("Boss", admin=True)

    directory_sync.sync_directory(db, [member(asha.slack_user_id, asha.email, "Asha")])

    for person in (asha, ravi, meena, boss):
        db.refresh(person)
    assert (asha.active, ravi.active, meena.active, boss.active) == (True, False, False, True)
    assert count(db) == 4  # nobody is deleted
    assert audit(db, "directory.sync")[0].details["deactivated"] == 2


def test_someone_who_comes_back_in_slack_is_active_again_and_counted(directory, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    directory_sync.sync_directory(db, [member(asha.slack_user_id, asha.email, "Asha")])
    db.refresh(ravi)
    assert ravi.active is False

    directory_sync.sync_directory(db, [member(asha.slack_user_id, asha.email, "Asha"), member(ravi.slack_user_id, ravi.email, "Ravi")])

    db.refresh(ravi)
    assert ravi.active is True
    assert audit(db, "directory.sync")[-1].details["reactivated"] == 1


def test_a_deactivated_person_is_not_offered_in_the_picker_and_cannot_sign_in(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)

    directory_sync.sync_directory(db, [member(admin.slack_user_id, admin.email, "Admin"), member(asha.slack_user_id, asha.email, "Asha")])

    picker = directory.call(asha, "GET", "/people", params={"unassigned": True}).json()["items"]
    assert "Ravi" not in [p["name"] for p in picker]
    assert directory.call(ravi, "GET", "/me").json()["detail"]["code"] == "not_onboarded"


def test_a_deactivated_person_still_on_a_team_is_counted(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    db.expire_all()

    directory_sync.sync_directory(db, [member(asha.slack_user_id, asha.email, "Asha"), member(admin.slack_user_id, admin.email, "Admin")])

    assert audit(db, "directory.sync")[0].details["deactivated_on_a_team"] == 1


def test_a_slack_email_that_already_belongs_to_another_person_here_is_skipped_and_the_run_does_not_break(directory, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")

    directory_sync.sync_directory(db, [
        member(asha.slack_user_id, asha.email, "Asha"),
        member("UOTHER", ravi.email, "A different Slack account with Ravi's address"),  # would break the unique email
    ])

    db.refresh(ravi)
    assert ravi.email == "ravi@atimotors.com"  # his row is not rewritten, and the new account is not added
    assert count(db, Person.slack_user_id == "UOTHER") == 0
    assert any("already belongs to another person" in n for n in audit(db, "directory.sync")[0].details["notes"])


def test_a_person_still_in_slack_with_no_usable_email_is_not_treated_as_having_left(directory, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")

    directory_sync.sync_directory(db, [
        member(asha.slack_user_id, asha.email, "Asha"),
        {"id": ravi.slack_user_id, "profile": {"email": "", "display_name": "Ravi"}},  # Slack shows no email for him today
    ])

    db.refresh(ravi)
    assert ravi.active is True and ravi.email == "ravi@atimotors.com"  # untouched, not deactivated
    assert audit(db, "directory.sync")[0].details["skipped"] == 1


# ---- the safety limits ----

def test_a_run_that_would_remove_too_many_people_is_refused_unless_forced(directory, db):
    for n in range(25):
        directory.person(f"Person{n:02d}")
    keep = member("UKEEP", "keep@atimotors.com", "Keep")

    with pytest.raises(AppError) as err:
        directory_sync.sync_directory(db, [keep])
    assert err.value.code == "directory_removal_too_large"
    assert count(db, Person.active.is_(True)) == 25  # nothing was changed
    assert count(db, Person.slack_user_id == "UKEEP") == 0 and audit(db, "directory.sync") == []

    directory_sync.sync_directory(db, [keep], allow_large_removal=True)
    assert count(db, Person.active.is_(True)) == 1 and count(db, Person.slack_user_id == "UKEEP") == 1


def test_a_slack_list_with_nobody_usable_changes_nothing(directory, db):
    directory.person("Asha")

    with pytest.raises(AppError) as err:
        directory_sync.sync_directory(db, [member("UBOT", "bot@atimotors.com", "A bot", is_bot=True)])

    assert (err.value.code, err.value.status_code) == ("directory_empty", 502)
    assert count(db, Person.active.is_(True)) == 1 and audit(db, "directory.sync") == []


# ---- the first admin ----

def test_the_bootstrap_admins_are_made_admin_once_and_audited(monkeypatch, db):
    monkeypatch.setattr(settings, "bootstrap_admin_emails", "boss@atimotors.com")
    slack = [member("U1", "boss@atimotors.com", "Boss")]

    directory_sync.sync_directory(db, slack)
    directory_sync.sync_directory(db, slack)

    boss = db.scalar(select(Person).where(Person.email == "boss@atimotors.com"))
    assert boss.is_admin is True
    grants = audit(db, "admin.grant")
    assert [(g.person_id, g.actor_id) for g in grants] == [(boss.id, None)]  # once, by no person
    assert audit(db, "directory.sync")[0].details["new_admins"] == ["boss@atimotors.com"]


def test_a_bootstrap_admin_who_is_not_in_slack_is_reported_and_does_not_stop_the_run(monkeypatch, db):
    monkeypatch.setattr(settings, "bootstrap_admin_emails", "ghost@atimotors.com")

    directory_sync.sync_directory(db, [member("U1", "asha@atimotors.com", "Asha")])

    assert count(db) == 1
    assert audit(db, "directory.sync")[0].details["missing_admins"] == ["ghost@atimotors.com"]


def test_the_run_shows_in_the_admins_audit_log_as_the_servers_own(directory, admin, db):
    directory_sync.sync_directory(db, [member(admin.slack_user_id, admin.email, "Admin"), member("U9", "new@atimotors.com", "New Joiner")])

    entries = directory.call(admin, "GET", "/audit-log").json()["items"]

    run = next(e for e in entries if e["action"] == "directory.sync")
    assert run["actor_name"] is None and run["reason"] == "Weekly Slack sync" and run["details"]["added"] == 1


# ---- the admin's "Sync people from Slack" ----

@pytest.fixture
def slack_people(admin, monkeypatch):
    """Slack is set up and lists the admin and one new joiner."""
    state = {"members": [member(admin.slack_user_id, admin.email, "Admin"), member("UNEW", "new@atimotors.com", "New Joiner")]}
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(client, "list_users", lambda token: state["members"])
    return state


def test_an_admin_syncs_the_people_and_the_run_is_recorded_under_their_name(directory, admin, slack_people, db):
    res = directory.call(admin, "POST", "/people/sync")

    assert res.status_code == 200
    assert res.json() == {"people": 2, "added": 1, "reactivated": 0, "deactivated": 0, "deactivated_on_a_team": 0, "new_admins": 0, "skipped": 0}
    [run] = audit(db, "directory.sync")
    assert run.actor_id == admin.id and run.reason == "Run from the Teams portal"
    assert db.scalar(select(Person).where(Person.email == "new@atimotors.com")) is not None
    entries = directory.call(admin, "GET", "/audit-log").json()["items"]
    assert next(e for e in entries if e["action"] == "directory.sync")["actor_name"] == "Admin"  # the Who column names the admin


def test_nobody_but_an_admin_may_sync_the_people(directory, admin, slack_people, db):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)

    assert directory.call(None, "POST", "/people/sync").status_code == 401
    assert directory.call(asha, "POST", "/people/sync").status_code == 403  # a manager
    assert directory.call(directory.person("Ravi"), "POST", "/people/sync").status_code in (401, 403)  # a plain member
    assert audit(db, "directory.sync") == []


def test_the_button_says_why_when_slack_is_not_set_up_or_cannot_be_read(directory, admin, slack_people, monkeypatch):
    def refuse(token):
        raise client.SlackError("Slack refused it: ratelimited.")

    monkeypatch.setattr(client, "list_users", refuse)
    res = directory.call(admin, "POST", "/people/sync")
    assert (res.status_code, res.json()["detail"]["code"]) == (502, "slack_failed")

    monkeypatch.setattr(settings, "slack_bot_token", "")
    res = directory.call(admin, "POST", "/people/sync")
    assert (res.status_code, res.json()["detail"]["code"]) == (501, "slack_not_configured")


def test_a_run_that_would_remove_too_many_people_is_refused_from_the_button_with_the_way_to_force_it(directory, admin, slack_people, db):
    for n in range(25):
        directory.person(f"Person{n:02d}")

    res = directory.call(admin, "POST", "/people/sync")

    assert (res.status_code, res.json()["detail"]["code"]) == (409, "directory_removal_too_large")
    assert count(db, Person.active.is_(True)) == 26  # nothing changed, and the button has no way to force it


def test_an_answer_from_slack_with_nobody_usable_is_a_502_and_changes_nothing(directory, admin, slack_people, db):
    slack_people["members"] = [member("UBOT", "bot@atimotors.com", "A bot", is_bot=True)]

    res = directory.call(admin, "POST", "/people/sync")

    assert (res.status_code, res.json()["detail"]["code"]) == (502, "directory_empty")
    assert audit(db, "directory.sync") == []


def test_an_admin_can_press_the_button_three_times_a_minute_and_the_fourth_is_a_429(directory, admin, slack_people):
    from security import rate_limit

    assert rate_limit.DIRECTORY_SYNC_PER_MINUTE == 3

    codes = [directory.call(admin, "POST", "/people/sync").status_code for _ in range(4)]

    assert codes == [200, 200, 200, 429]
    assert directory.call(admin, "GET", "/me").status_code == 200  # the rest of the API is not affected


# ---- the paged Slack call ----

def test_the_workspace_list_follows_slacks_pages_until_there_is_no_next_cursor(monkeypatch):
    pages = {
        "": {"members": [{"id": "U1"}, {"id": "U2"}], "response_metadata": {"next_cursor": "c2"}},
        "c2": {"members": [{"id": "U3"}], "response_metadata": {"next_cursor": ""}},
    }
    asked = []

    def fake_call(token, method, *, data=None, json=None):
        asked.append((method, data.get("cursor", ""), data["limit"]))
        return pages[data.get("cursor", "")]

    monkeypatch.setattr(client, "_call", fake_call)

    assert [m["id"] for m in client.list_users("xoxb-test")] == ["U1", "U2", "U3"]
    assert asked == [("users.list", "", 200), ("users.list", "c2", 200)]


def test_a_list_that_never_ends_is_an_error_not_a_short_list(monkeypatch):
    monkeypatch.setattr(client, "_call", lambda *a, **k: {"members": [{"id": "U1"}], "response_metadata": {"next_cursor": "more"}})

    with pytest.raises(client.SlackError):
        client.list_users("xoxb-test")


# ---- the runner ----

def test_the_runner_syncs_from_slack_and_says_what_it_did(directory, monkeypatch, capsys):
    from identity import directory_scheduler

    asha = directory.person("Asha")
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(client, "list_users", lambda token: [member(asha.slack_user_id, asha.email, "Asha"), member("U9", "new@atimotors.com", "New")])

    assert directory_scheduler.run_once() is True

    out = capsys.readouterr().out
    assert "2 people in Slack, 1 added" in out


def test_the_runner_does_nothing_and_says_so_when_slack_is_not_set_up(monkeypatch, capsys, db):
    from identity import directory_scheduler

    monkeypatch.setattr(settings, "slack_bot_token", "")

    assert directory_scheduler.run_once() is False
    assert "SLACK_BOT_TOKEN is not set" in capsys.readouterr().out
    assert audit(db, "directory.sync") == []
    assert directory_scheduler.main(["--once"]) == 0  # not an error: a stack without Slack still starts


def test_a_failed_run_is_logged_and_main_once_exits_non_zero(monkeypatch, caplog):
    from identity import directory_scheduler

    def refuse(token):
        raise client.SlackError("Slack refused it: ratelimited.")

    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(client, "list_users", refuse)

    with caplog.at_level("ERROR"):
        assert directory_scheduler.main(["--once"]) == 1
    assert "Slack could not be read" in caplog.text


def test_a_refused_run_is_logged_and_can_be_forced_by_hand(directory, monkeypatch, caplog):
    from identity import directory_scheduler

    for n in range(25):
        directory.person(f"Person{n:02d}")
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(client, "list_users", lambda token: [member("UKEEP", "keep@atimotors.com", "Keep")])

    with caplog.at_level("ERROR"):
        assert directory_scheduler.main(["--once"]) == 1
    assert "refused" in caplog.text

    assert directory_scheduler.main(["--once", "--allow-large-removal"]) == 0


def test_the_schedule_is_read_from_the_environment_in_the_shared_format():
    from core.schedule import parse_schedule

    [(days, at)] = parse_schedule("sun 22:00")

    assert days == frozenset({6}) and (at.hour, at.minute) == (22, 0)
