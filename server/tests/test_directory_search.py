"""GET /people: the directory behind the 'Add person' picker."""
from sqlalchemy import func, select

from models import Person
from tests.conftest import make_team

# Paging (limit, offset, total) is covered in test_pagination.py.


def names(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [person["name"] for person in response.json()["items"]]


def search(directory, who, **params):
    return directory.call(who, "GET", "/people", params=params)


def test_search_matches_part_of_a_name_ignoring_case(directory, admin):
    directory.person("Asha Kumar", email="a.kumar@atimotors.com")
    directory.person("Ravi Nair", email="r.nair@atimotors.com")

    assert names(search(directory, admin, q="ASHA")) == ["Asha Kumar"]
    assert names(search(directory, admin, q="kumar")) == ["Asha Kumar"]
    assert names(search(directory, admin, q="ravi nair")) == ["Ravi Nair"]


def test_search_matches_part_of_an_email_even_when_the_name_differs(directory, admin):
    directory.person("Meena Rao", email="mrao.eng@atimotors.com")
    directory.person("Zed Brown", email="zbrown@atimotors.com")

    assert names(search(directory, admin, q="mrao.eng")) == ["Meena Rao"]
    assert names(search(directory, admin, q="ZBROWN@ATI")) == ["Zed Brown"]
    assert names(search(directory, admin, q="@atimotors.com")) == ["Admin", "Meena Rao", "Zed Brown"]


def test_admins_filter_lists_only_admins_including_those_on_no_team(directory, admin):
    ravi = directory.person("Ravi")
    directory.person("Zoe")
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    directory.call(admin, "PATCH", f"/people/{ravi.id}/admin", json={"is_admin": True, "reason": "dashboards"})
    directory.call(admin, "PATCH", f"/people/{asha.id}/admin", json={"is_admin": True, "reason": "runs NPI"})

    assert names(search(directory, admin, admins="true")) == ["Admin", "Asha", "Ravi"]  # Ravi is on no team, Asha is on one
    assert names(search(directory, admin, admins="true", q="rav")) == ["Ravi"]
    assert names(search(directory, admin, admins="false", q="zoe")) == ["Zoe"]


def test_an_admin_with_no_team_can_be_added_and_removed_without_joining_a_team(directory, admin, db):
    ravi = directory.person("Ravi")

    grant = directory.call(admin, "PATCH", f"/people/{ravi.id}/admin", json={"is_admin": True, "reason": "dashboards"})
    assert grant.status_code == 200 and grant.json()["team_id"] is None and grant.json()["is_admin"] is True
    assert directory.call(ravi, "GET", "/teams").status_code == 200  # they can now use the admin screens
    revoke = directory.call(admin, "PATCH", f"/people/{ravi.id}/admin", json={"is_admin": False, "reason": "moved on"})
    assert revoke.status_code == 200 and revoke.json()["is_admin"] is False


def test_only_an_admin_can_add_or_remove_an_admin(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)

    for who in (asha, ravi):
        res = directory.call(who, "PATCH", f"/people/{ravi.id}/admin", json={"is_admin": True, "reason": "x"})
        assert (res.status_code, res.json()["detail"]["code"]) in ((403, "forbidden"), (403, "not_onboarded"))
    assert names(search(directory, admin, admins="true")) == ["Admin"]


def test_a_blank_search_returns_everyone_and_spaces_are_trimmed(directory, admin):
    directory.person("Asha")
    assert names(search(directory, admin, q="   ")) == ["Admin", "Asha"]
    assert names(search(directory, admin, q="  asha  ")) == ["Asha"]
    assert names(search(directory, admin)) == ["Admin", "Asha"]


def test_a_search_with_no_match_is_an_empty_list(directory, admin):
    directory.person("Asha")
    assert names(search(directory, admin, q="nobody-by-this-name")) == []


def test_quotes_and_sql_look_alikes_are_treated_as_plain_text(directory, admin, db):
    directory.person("Zed O'Brien")

    assert names(search(directory, admin, q="O'Brien")) == ["Zed O'Brien"]
    assert names(search(directory, admin, q="'; DROP TABLE people; --")) == []
    assert db.scalar(select(func.count()).select_from(Person)) == 2  # the table and its rows are intact


def test_percent_and_underscore_are_matched_literally_not_as_wildcards(directory, admin):
    directory.person("Asha")
    directory.person("Fifty%Off")
    directory.person("a_b")

    assert names(search(directory, admin, q="%")) == ["Fifty%Off"]
    assert names(search(directory, admin, q="_")) == ["a_b"]


def test_results_are_ordered_by_name(directory, admin):
    for name in ("Zed", "Asha", "Meena"):
        directory.person(name)
    assert names(search(directory, admin)) == ["Admin", "Asha", "Meena", "Zed"]


def test_the_default_list_includes_people_on_teams_but_not_inactive_ones(directory, admin, db):
    asha, ravi, sleepy = directory.person("Asha"), directory.person("Ravi"), directory.person("Sleepy")
    sleepy.active = False
    db.commit()
    make_team(directory, admin, "NPI", asha)

    rows = search(directory, admin).json()["items"]
    assert sorted(p["name"] for p in rows) == ["Admin", "Asha", "Ravi"]
    assert {p["name"]: p["team_name"] for p in rows} == {"Admin": None, "Asha": "NPI", "Ravi": None}


def test_unassigned_hides_people_on_teams_and_inactive_ones_but_shows_admins(directory, admin, db):
    asha, ravi, sleepy = directory.person("Asha"), directory.person("Ravi"), directory.person("Sleepy")
    directory.person("Helper", admin=True)
    sleepy.active = False
    db.commit()
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})

    assert names(search(directory, asha, unassigned=True)) == ["Admin", "Helper"]

