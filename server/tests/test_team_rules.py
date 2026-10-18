"""Edge cases of creating teams and changing managers: who is refused, and that a refusal changes nothing."""
from sqlalchemy import select

from models import AccessAuditLog, Team
from tests.conftest import make_team


def codes(response) -> str:
    return response.json()["detail"]["code"]


def change_manager(directory, admin, team, person):
    return directory.call(
        admin, "PATCH", f"/teams/{team['id']}/manager", json={"person_id": str(person.id), "reason": "swap"}
    )


def test_making_the_current_manager_the_manager_again_is_refused(directory, admin):
    asha = directory.person("Asha")
    team = make_team(directory, admin, "NPI", asha)

    res = change_manager(directory, admin, team, asha)
    assert res.status_code == 409 and codes(res) == "same_manager"


def test_an_inactive_person_cannot_start_a_team_or_become_a_manager(directory, admin, db):
    asha, sleepy = directory.person("Asha"), directory.person("Sleepy")
    sleepy.active = False
    db.commit()
    team = make_team(directory, admin, "NPI", asha)

    create = directory.call(
        admin, "POST", "/teams", json={"name": "QA", "initial_manager_person_id": str(sleepy.id), "reason": "r"}
    )
    change = change_manager(directory, admin, team, sleepy)
    assert (create.status_code, codes(create)) == (409, "person_inactive")
    assert (change.status_code, codes(change)) == (409, "person_inactive")


def test_a_member_of_another_team_cannot_become_this_teams_manager(directory, admin):
    npi = make_team(directory, admin, "NPI", directory.person("Asha"))
    qa_manager, qa_member = directory.person("Ravi"), directory.person("Meena")
    qa = make_team(directory, admin, "QA", qa_manager)
    directory.call(admin, "POST", f"/teams/{qa['id']}/members", json={"person_id": str(qa_member.id), "reason": "r"})

    res = change_manager(directory, admin, npi, qa_member)
    assert res.status_code == 409 and codes(res) == "already_on_team"


def test_a_refused_manager_change_leaves_everything_as_it_was(directory, admin, db):
    asha, sleepy = directory.person("Asha"), directory.person("Sleepy")
    sleepy.active = False
    db.commit()
    team = make_team(directory, admin, "NPI", asha)

    change_manager(directory, admin, team, sleepy)

    db.refresh(asha)
    assert asha.role == "manager"
    assert str(db.get(Team, team["id"]).manager_id) == str(asha.id)
    actions = db.scalars(select(AccessAuditLog.action)).all()
    assert actions == ["team.create"], "a refused change must not be audited"


def test_a_refused_create_does_not_promote_the_person(directory, admin, db):
    make_team(directory, admin, "NPI", directory.person("Asha"))
    ravi = directory.person("Ravi")

    res = directory.call(
        admin, "POST", "/teams", json={"name": "npi", "initial_manager_person_id": str(ravi.id), "reason": "r"}
    )

    assert res.status_code == 409 and codes(res) == "team_name_taken"
    db.refresh(ravi)
    assert ravi.role == "member" and ravi.team_id is None
    assert db.scalar(select(AccessAuditLog).where(AccessAuditLog.person_id == ravi.id)) is None


def test_an_admin_on_no_team_can_start_a_team_and_stays_admin(directory, admin):
    boss = directory.person("Boss", admin=True)

    team = make_team(directory, admin, "NPI", boss)

    assert team["manager"]["id"] == str(boss.id)
    assert team["manager"]["role"] == "manager" and team["manager"]["is_admin"] is True


def test_a_team_with_no_manager_can_be_given_one(directory, admin, db):
    orphan = Team(name="Orphan")
    db.add(orphan)
    db.commit()
    ravi = directory.person("Ravi")

    res = directory.call(
        admin, "PATCH", f"/teams/{orphan.id}/manager", json={"person_id": str(ravi.id), "reason": "first manager"}
    )

    assert res.status_code == 200 and res.json()["manager"]["id"] == str(ravi.id)
    entry = db.scalar(select(AccessAuditLog).where(AccessAuditLog.action == "team.manager_change"))
    assert entry.details == {"old_manager_id": None, "new_manager_id": str(ravi.id)}


def test_the_member_count_follows_adds_and_removes(directory, admin):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    team = make_team(directory, admin, "NPI", asha)

    def count():
        return directory.call(admin, "GET", "/teams").json()[0]["member_count"]

    assert count() == 1
    for person in (ravi, meena):
        directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})
    assert count() == 3
    directory.call(asha, "DELETE", f"/teams/{team['id']}/members/{ravi.id}")
    assert count() == 2
