"""GET /dev/accounts: the dev sign-in list. It needs no sign-in, so it must vanish when DEV_AUTH is off."""
from core.config import settings
from tests.conftest import make_team


def accounts(directory):
    res = directory.call(None, "GET", "/dev/accounts")
    assert res.status_code == 200, res.text
    return {a["name"]: a for a in res.json()}


def test_it_lists_admins_and_managers_who_can_sign_in_without_signing_in_first(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    directory.person("Loner")  # on no team: not offered at all

    listed = accounts(directory)

    assert listed["Admin"] == {"email": "admin@atimotors.com", "name": "Admin", "can_sign_in": True}
    assert listed["Asha"]["can_sign_in"] is True
    assert "Loner" not in listed and "Ravi" not in listed


def test_a_few_plain_team_members_are_listed_as_refused(directory, admin):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)
    people = [directory.person(name) for name in ("Bina", "Chet", "Dev")]
    for person in people:
        directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})

    listed = accounts(directory)

    refused = sorted(name for name, a in listed.items() if not a["can_sign_in"])
    assert refused == ["Bina", "Chet"]  # two examples, by name
    # and the server really does refuse them
    assert directory.call(people[0], "GET", "/me").json()["detail"]["code"] == "not_onboarded"


def test_inactive_people_are_not_offered(directory, admin, db):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    asha.active = False
    db.commit()

    assert "Asha" not in accounts(directory)


def test_it_is_a_404_when_dev_auth_is_off(directory, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)

    res = directory.call(None, "GET", "/dev/accounts")

    assert (res.status_code, res.json()["detail"]["code"]) == (404, "not_found")
