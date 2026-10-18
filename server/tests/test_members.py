from tests.conftest import make_team


def test_manager_adds_a_person_from_the_directory(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)

    def picker_names():
        rows = directory.call(asha, "GET", "/people", params={"unassigned": True}).json()["items"]
        return [p["name"] for p in rows]

    # The admin has no team either, so they are in the picker too; Asha already runs NPI and is not.
    assert picker_names() == ["Admin", "Ravi"]

    res = directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    assert res.status_code == 201, res.text
    assert res.json()["team_name"] == "NPI"
    assert picker_names() == ["Admin"]


def test_manager_cannot_touch_another_team(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    qa = make_team(directory, admin, "QA", ravi)
    joiner = directory.person("Meena")

    res = directory.call(asha, "POST", f"/teams/{qa['id']}/members", json={"person_id": str(joiner.id)})
    assert res.status_code == 403
    assert directory.call(asha, "GET", f"/teams/{qa['id']}/members").status_code == 403


def test_a_person_is_on_at_most_one_team(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    npi = make_team(directory, admin, "NPI", asha)
    qa = make_team(directory, admin, "QA", ravi)
    joiner = directory.person("Meena")
    directory.call(asha, "POST", f"/teams/{npi['id']}/members", json={"person_id": str(joiner.id)})

    res = directory.call(ravi, "POST", f"/teams/{qa['id']}/members", json={"person_id": str(joiner.id)})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "already_on_team"


def test_adding_a_member_needs_no_reason_from_an_admin_or_a_manager(directory, admin):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    team = make_team(directory, admin, "NPI", asha)

    by_admin = directory.call(admin, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    assert by_admin.status_code == 201
    by_manager = directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(meena.id)})
    assert by_manager.status_code == 201


def test_members_list_puts_the_manager_first(directory, admin):
    # Alphabetically Asha < Ravi < Zed, so only the ordering rule can put Zed first.
    zed, asha, ravi = directory.person("Zed"), directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", zed)
    for person in (asha, ravi):
        directory.call(zed, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})

    names = [p["name"] for p in directory.call(zed, "GET", f"/teams/{team['id']}/members").json()]
    assert names == ["Zed", "Asha", "Ravi"]


def test_removed_person_goes_back_to_the_picker(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})

    gone = directory.call(asha, "DELETE", f"/teams/{team['id']}/members/{ravi.id}")
    assert gone.status_code == 204
    assert [p["name"] for p in directory.call(asha, "GET", f"/teams/{team['id']}/members").json()] == ["Asha"]
    picker = directory.call(asha, "GET", "/people", params={"unassigned": True}).json()["items"]
    assert "Ravi" in [p["name"] for p in picker]


def test_the_manager_cannot_be_removed(directory, admin):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    blocked = directory.call(admin, "DELETE", f"/teams/{team['id']}/members/{asha.id}", json={"reason": "x"})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "is_manager"


def test_the_activate_route_is_gone(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})

    res = directory.call(asha, "PATCH", f"/teams/{team['id']}/members/{ravi.id}", json={"active": False})
    assert res.status_code == 405


def test_an_admin_on_no_team_can_be_added_as_a_member_and_a_manager_cannot(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    npi = make_team(directory, admin, "NPI", asha)
    qa = make_team(directory, admin, "QA", ravi)
    helper_admin = directory.person("Helper", admin=True)

    added = directory.call(asha, "POST", f"/teams/{npi['id']}/members", json={"person_id": str(helper_admin.id)})
    assert added.status_code == 201
    assert added.json()["is_admin"] is True and added.json()["role"] == "member"

    # Ravi runs QA, so he is on a team and cannot be added to another one.
    res = directory.call(asha, "POST", f"/teams/{npi['id']}/members", json={"person_id": str(ravi.id)})
    assert res.status_code == 409 and qa["manager"]["id"] == str(ravi.id)


def test_a_manager_can_be_listed_as_a_team_member_to_assign_to(directory, admin):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    members = directory.call(asha, "GET", f"/teams/{team['id']}/members").json()
    assert [m["id"] for m in members] == [str(asha.id)]
