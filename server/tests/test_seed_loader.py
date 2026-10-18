import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from models import AccessAuditLog, Person
from tests.conftest import make_team

# seed/load_db.py is a script, not a package, so load it from its path.
_path = Path(__file__).resolve().parents[2] / "seed" / "load_db.py"
_spec = importlib.util.spec_from_file_location("load_db", _path)
load_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_db)


def row(slack_id: str, email: str, name: str) -> dict:
    """One entry of the directory extract."""
    return {"slack_user_id": slack_id, "email": email, "display_name": name}


def write_directory(tmp_path, rows: list[dict]) -> Path:
    path = tmp_path / "people.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_read_directory_accepts_the_people_json_shape_as_well_as_the_slack_extract(tmp_path):
    path = write_directory(tmp_path, [
        {"id": "p1", "displayName": "Asha", "email": "Asha@atimotors.com", "slackUserId": "U1", "teamId": None},
        row("U2", "ravi@atimotors.com", "Ravi"),
    ])

    rows, skipped = load_db.read_directory(path)

    assert rows == [
        {"slack_user_id": "U1", "email": "asha@atimotors.com", "name": "Asha"},
        {"slack_user_id": "U2", "email": "ravi@atimotors.com", "name": "Ravi"},
    ]
    assert skipped == []


def test_read_directory_keeps_good_rows_and_says_why_it_skipped_the_rest(tmp_path):
    path = write_directory(tmp_path, [
        row("U1", "  Asha@AtiMotors.com ", " Asha "),
        row("U2", "ravi@atimotors.com", ""),
        row("U3", "outsider@gmail.com", "Outsider"),
        row("U4", "asha@atimotors.com", "Asha again"),
        row("U1", "other@atimotors.com", "Same Slack id"),
        row("U5", "meena@atimotors.com", "Meena"),
    ])

    rows, skipped = load_db.read_directory(path)

    assert rows == [
        {"slack_user_id": "U1", "email": "asha@atimotors.com", "name": "Asha"},
        {"slack_user_id": "U5", "email": "meena@atimotors.com", "name": "Meena"},
    ]
    assert len(skipped) == 4
    assert any("missing" in note for note in skipped)
    assert any("not @atimotors.com" in note for note in skipped)
    assert sum("duplicate" in note for note in skipped) == 2


def test_a_missing_directory_file_stops_with_a_clear_message(tmp_path):
    with pytest.raises(SystemExit) as stop:
        load_db.read_directory(tmp_path / "nope.json")
    assert "is missing" in str(stop.value)


def test_loading_twice_adds_nobody_new(db):
    rows = [
        {"slack_user_id": "U1", "email": "asha@atimotors.com", "name": "Asha"},
        {"slack_user_id": "U2", "email": "ravi@atimotors.com", "name": "Ravi"},
    ]
    for _ in range(2):
        load_db.upsert_people(db, rows)
        db.commit()

    assert db.scalar(select(func.count()).select_from(Person)) == 2


def test_a_reload_refreshes_name_and_email_but_never_role_team_or_admin(directory, admin, db):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    load_db.upsert_people(db, [{"slack_user_id": asha.slack_user_id, "email": "asha.k@atimotors.com", "name": "Asha K"}])
    db.commit()

    db.refresh(asha)
    assert (asha.name, asha.email) == ("Asha K", "asha.k@atimotors.com")
    assert asha.role == "manager" and str(asha.team_id) == team["id"]


def test_people_missing_from_the_file_are_deactivated_not_deleted(directory, db):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")

    left = load_db.deactivate_missing(db, {asha.slack_user_id})
    db.commit()

    assert {p.name for p in left} == {"Ravi", "Meena"}
    for person in (asha, ravi, meena):
        db.refresh(person)
    assert (asha.active, ravi.active, meena.active) == (True, False, False)
    assert db.scalar(select(func.count()).select_from(Person)) == 3


def test_an_admin_missing_from_the_file_is_never_deactivated(directory, db):
    boss = directory.person("Boss", admin=True)

    assert load_db.deactivate_missing(db, set()) == []
    db.refresh(boss)
    assert boss.active is True


def test_someone_who_comes_back_in_the_file_is_active_again(directory, db):
    ravi = directory.person("Ravi")
    load_db.deactivate_missing(db, set())
    db.commit()

    load_db.upsert_people(db, [{"slack_user_id": ravi.slack_user_id, "email": ravi.email, "name": "Ravi"}])
    db.commit()

    db.refresh(ravi)
    assert ravi.active is True


def test_a_deactivated_person_is_not_offered_in_the_picker_and_cannot_sign_in(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    load_db.deactivate_missing(db, {admin.slack_user_id, asha.slack_user_id})
    db.commit()

    picker = directory.call(asha, "GET", "/people", params={"unassigned": True}).json()["items"]
    assert "Ravi" not in [p["name"] for p in picker]
    assert directory.call(ravi, "GET", "/me").json()["detail"]["code"] == "not_onboarded"


def test_a_file_that_would_remove_too_many_people_is_refused_unless_forced(directory, db):
    for n in range(25):
        directory.person(f"Person{n:02d}")

    with pytest.raises(SystemExit) as stop:
        load_db.deactivate_missing(db, set())
    assert "--allow-large-removal" in str(stop.value)
    assert db.scalar(select(func.count()).select_from(Person).where(Person.active.is_(True))) == 25

    assert len(load_db.deactivate_missing(db, set(), allow_large_removal=True)) == 25


def test_a_deactivated_person_still_on_a_team_is_reported(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    db.expire_all()  # the API wrote through another session; this one must re-read, as the real script does

    left = load_db.deactivate_missing(db, {admin.slack_user_id, asha.slack_user_id})

    assert [(p.name, p.team_id is not None) for p in left] == [("Ravi", True)]


def test_bootstrap_admins_are_granted_once_and_audited(directory, db):
    ravi = directory.person("Ravi")

    assert load_db.grant_bootstrap_admins(db, [ravi.email]) == [ravi.email]
    db.commit()
    assert load_db.grant_bootstrap_admins(db, [ravi.email]) == []

    db.refresh(ravi)
    assert ravi.is_admin is True
    entries = db.scalars(select(AccessAuditLog).where(AccessAuditLog.person_id == ravi.id)).all()
    assert [(e.action, e.actor_id) for e in entries] == [("admin.grant", None)]


def test_a_bootstrap_admin_who_is_not_in_the_directory_stops_the_load(db):
    with pytest.raises(SystemExit) as stop:
        load_db.grant_bootstrap_admins(db, ["ghost@atimotors.com"])
    assert "not in the people directory" in str(stop.value)
