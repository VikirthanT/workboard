"""Edge cases of adding and removing people on a team."""
import uuid

import pytest

from core.exceptions import AppError
from identity.services import members
from tests.conftest import make_team


def codes(response) -> str:
    return response.json()["detail"]["code"]


def add(directory, who, team, person, **extra):
    return directory.call(who, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id), **extra})


def test_an_inactive_person_cannot_be_added(directory, admin, db):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))
    sleepy = directory.person("Sleepy")
    sleepy.active = False
    db.commit()

    res = add(directory, admin, team, sleepy, reason="r")
    assert res.status_code == 409 and codes(res) == "person_inactive"


def test_a_manager_role_person_cannot_be_added_as_a_member(directory, admin):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))
    odd = directory.person("Odd", role="manager")  # a manager on no team: not reachable through the API

    res = add(directory, admin, team, odd, reason="r")
    assert res.status_code == 409 and codes(res) == "person_unavailable"


def test_adding_someone_twice_is_refused_the_second_time(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)

    assert add(directory, asha, team, ravi).status_code == 201
    again = add(directory, asha, team, ravi)
    assert again.status_code == 409 and codes(again) == "already_on_team"


def test_removing_someone_who_is_not_on_the_team_is_a_404(directory, admin):
    npi = make_team(directory, admin, "NPI", directory.person("Asha"))
    qa = make_team(directory, admin, "QA", directory.person("Ravi"))
    stranger = directory.person("Stranger")
    other_team_member = directory.person("Meena")
    add(directory, admin, qa, other_team_member, reason="r")

    for person in (stranger, other_team_member):
        res = directory.call(admin, "DELETE", f"/teams/{npi['id']}/members/{person.id}", json={"reason": "r"})
        assert res.status_code == 404 and codes(res) == "not_on_team"


def test_an_admin_must_give_a_reason_to_remove_someone(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    add(directory, asha, team, ravi)
    path = f"/teams/{team['id']}/members/{ravi.id}"

    blank = directory.call(admin, "DELETE", path, json={"reason": " "})
    assert blank.status_code == 422 and codes(blank) == "reason_required"
    assert directory.call(admin, "DELETE", path, json={"reason": "moved to QA"}).status_code == 204


def test_an_admin_can_list_the_members_of_any_team(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    add(directory, asha, team, ravi)

    names = [p["name"] for p in directory.call(admin, "GET", f"/teams/{team['id']}/members").json()]
    assert names == ["Asha", "Ravi"]


def test_someone_removed_from_one_team_can_join_another(directory, admin):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    npi = make_team(directory, admin, "NPI", asha)
    qa = make_team(directory, admin, "QA", ravi)
    add(directory, asha, npi, meena)
    directory.call(asha, "DELETE", f"/teams/{npi['id']}/members/{meena.id}")

    res = add(directory, ravi, qa, meena)
    assert res.status_code == 201 and res.json()["team_name"] == "QA"


def test_get_member_refuses_someone_on_another_team(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    npi = make_team(directory, admin, "NPI", asha)
    make_team(directory, admin, "QA", ravi)
    db.expire_all()  # the API wrote through another session; re-read before calling the service directly

    assert members.get_member(db, uuid.UUID(npi["id"]), asha.id).id == asha.id
    with pytest.raises(AppError) as refused:
        members.get_member(db, uuid.UUID(npi["id"]), ravi.id)
    assert refused.value.code == "not_on_team"
