from tests.conftest import make_team


def test_create_team_promotes_initial_person(directory, admin, db):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    assert team["manager"]["id"] == str(asha.id)
    assert team["manager"]["role"] == "manager"
    assert team["manager"]["team_name"] == "NPI"
    assert team["member_count"] == 1


def test_create_team_needs_a_reason(directory, admin):
    asha = directory.person("Asha")
    res = directory.call(
        admin, "POST", "/teams", json={"name": "NPI", "initial_manager_person_id": str(asha.id), "reason": "  "}
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "reason_required"


def test_team_name_is_unique_ignoring_case(directory, admin):
    make_team(directory, admin, "NPI", directory.person("Asha"))
    res = directory.call(
        admin, "POST", "/teams",
        json={"name": "npi", "initial_manager_person_id": str(directory.person("Ravi").id), "reason": "x"},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "team_name_taken"


def test_person_on_another_team_cannot_start_a_team(directory, admin):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    res = directory.call(
        admin, "POST", "/teams", json={"name": "QA", "initial_manager_person_id": str(asha.id), "reason": "x"}
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "already_manager"


def test_changing_manager_demotes_the_old_one_and_keeps_them_on_the_team(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(admin, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id), "reason": "join"})

    res = directory.call(
        admin, "PATCH", f"/teams/{team['id']}/manager", json={"person_id": str(ravi.id), "reason": "handover"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["manager"]["id"] == str(ravi.id)

    db.refresh(asha)
    assert asha.role == "member"
    assert asha.team_id is not None  # still on the team


def test_cannot_make_someone_from_another_team_the_manager(directory, admin):
    npi = make_team(directory, admin, "NPI", directory.person("Asha"))
    qa_manager = directory.person("Ravi")
    make_team(directory, admin, "QA", qa_manager)
    res = directory.call(
        admin, "PATCH", f"/teams/{npi['id']}/manager", json={"person_id": str(qa_manager.id), "reason": "x"}
    )
    assert res.status_code == 409


def test_every_team_change_is_audited(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(admin, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id), "reason": "join"})
    directory.call(admin, "PATCH", f"/teams/{team['id']}/manager", json={"person_id": str(ravi.id), "reason": "swap"})

    entries = directory.call(admin, "GET", "/audit-log").json()["items"]
    assert [e["action"] for e in entries] == ["team.manager_change", "member.add", "team.create"]
    change = entries[0]
    assert change["details"] == {"old_manager_id": str(asha.id), "new_manager_id": str(ravi.id)}
    assert change["reason"] == "swap"


def test_manager_sees_only_their_own_team(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    make_team(directory, admin, "QA", ravi)

    names = [t["name"] for t in directory.call(asha, "GET", "/teams").json()]
    assert names == ["NPI"]
    assert len(directory.call(admin, "GET", "/teams").json()) == 2


def test_audit_entries_name_who_did_what_to_whom(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(admin, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id), "reason": "join"})

    added = directory.call(admin, "GET", "/audit-log").json()["items"][0]
    assert (added["actor_name"], added["person_name"], added["team_name"]) == ("Admin", "Ravi", "NPI")


def test_a_deleted_team_and_person_keep_their_names_in_the_log(directory, admin, db):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(admin, "DELETE", f"/teams/{team['id']}", json={"confirm_name": "NPI", "reason": "done"})
    db.delete(db.get(type(asha), asha.id))
    db.commit()

    deleted = directory.call(admin, "GET", "/audit-log").json()["items"][0]
    assert deleted["action"] == "team.delete"
    assert deleted["team_name"] == "NPI"  # the team row is gone; the name comes from the entry itself
    created = directory.call(admin, "GET", "/audit-log").json()["items"][1]
    assert created["person_name"] is None and created["actor_name"] == "Admin"  # the person is gone, nothing to show
