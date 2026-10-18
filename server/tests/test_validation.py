"""Bad input: malformed or missing fields (422 from the request models), ids that do not exist (404),
and the reason rules. The caller is always an admin, so a refusal is about the input, not permission."""
import pytest

from core.exceptions import AppError
from identity.services import audit
from tests.conftest import make_team

NOBODY = "00000000-0000-0000-0000-000000000000"


def codes(response) -> str:
    return response.json()["detail"]["code"]


# ---- malformed or missing input: the request models answer 422 ----

@pytest.mark.parametrize("body", [
    {},
    {"name": "NPI"},
    {"name": "NPI", "initial_manager_person_id": NOBODY},
    {"name": "NPI", "reason": "r"},
    {"name": "NPI", "initial_manager_person_id": "not-a-uuid", "reason": "r"},
    {"name": "", "initial_manager_person_id": NOBODY, "reason": "r"},
    {"name": "x" * 101, "initial_manager_person_id": NOBODY, "reason": "r"},
    {"name": "NPI", "initial_manager_person_id": NOBODY, "reason": "r" * 501},
    {"name": 7, "initial_manager_person_id": NOBODY, "reason": "r"},
], ids=["empty", "no manager", "no reason", "no name", "bad uuid", "empty name", "long name", "long reason", "name not text"])
def test_create_team_rejects_malformed_bodies(directory, admin, body):
    assert directory.call(admin, "POST", "/teams", json=body).status_code == 422


def test_create_team_without_any_body_is_422(directory, admin):
    assert directory.call(admin, "POST", "/teams").status_code == 422


def test_a_blank_name_made_of_spaces_is_refused_by_the_service(directory, admin):
    asha = directory.person("Asha")
    res = directory.call(
        admin, "POST", "/teams", json={"name": "   ", "initial_manager_person_id": str(asha.id), "reason": "r"}
    )
    assert res.status_code == 422 and codes(res) == "name_required"


@pytest.mark.parametrize("path", [
    "/teams/not-a-uuid",
    "/teams/not-a-uuid/members",
    "/teams/not-a-uuid/manager",
    f"/teams/{NOBODY}/members/not-a-uuid",
    "/people/not-a-uuid/admin",
])
def test_a_malformed_id_in_the_path_is_422(directory, admin, path):
    checked = 0
    for method in ("GET", "DELETE", "PATCH"):
        res = directory.call(admin, method, path, json={"confirm_name": "x", "reason": "r", "is_admin": True})
        if res.status_code != 405:  # not every path has every method
            assert res.status_code == 422, (method, path)
            checked += 1
    assert checked >= 1, f"no method answered for {path}, so nothing was checked"


def test_the_admin_toggle_needs_a_real_boolean(directory, admin):
    ravi = directory.person("Ravi")
    for body in ({"reason": "r"}, {"is_admin": "maybe", "reason": "r"}, {"is_admin": True}):
        assert directory.call(admin, "PATCH", f"/people/{ravi.id}/admin", json=body).status_code == 422


def test_delete_team_needs_a_confirmation_name_and_reason(directory, admin):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))
    for body in (None, {}, {"confirm_name": "NPI"}, {"reason": "r"}, {"confirm_name": "", "reason": "r"}):
        kwargs = {"json": body} if body is not None else {}
        assert directory.call(admin, "DELETE", f"/teams/{team['id']}", **kwargs).status_code == 422


def test_unknown_fields_in_a_body_are_ignored_not_applied(directory, admin, db):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)

    res = directory.call(
        asha, "POST", f"/teams/{team['id']}/members",
        json={"person_id": str(ravi.id), "role": "manager", "is_admin": True, "team_id": NOBODY},
    )

    assert res.status_code == 201
    db.refresh(ravi)
    # Mass assignment: the extra fields must not have changed the person.
    assert ravi.role == "member" and ravi.is_admin is False and str(ravi.team_id) == team["id"]


# ---- ids that do not exist: 404 with a code ----

def test_unknown_team_is_404_everywhere(directory, admin):
    person = directory.person("Ravi")
    attempts = [
        ("GET", f"/teams/{NOBODY}/members", None),
        ("POST", f"/teams/{NOBODY}/members", {"person_id": str(person.id), "reason": "r"}),
        ("DELETE", f"/teams/{NOBODY}/members/{person.id}", {"reason": "r"}),
        ("PATCH", f"/teams/{NOBODY}/manager", {"person_id": str(person.id), "reason": "r"}),
        ("DELETE", f"/teams/{NOBODY}", {"confirm_name": "x", "reason": "r"}),
    ]
    for method, path, body in attempts:
        res = directory.call(admin, method, path, **({"json": body} if body else {}))
        assert res.status_code == 404 and codes(res) == "team_not_found", (method, path)


def test_unknown_person_is_404_everywhere(directory, admin):
    team = make_team(directory, admin, "NPI", directory.person("Asha"))
    attempts = [
        ("POST", "/teams", {"name": "QA", "initial_manager_person_id": NOBODY, "reason": "r"}),
        ("POST", f"/teams/{team['id']}/members", {"person_id": NOBODY, "reason": "r"}),
        ("DELETE", f"/teams/{team['id']}/members/{NOBODY}", {"reason": "r"}),
        ("PATCH", f"/teams/{team['id']}/manager", {"person_id": NOBODY, "reason": "r"}),
        ("PATCH", f"/people/{NOBODY}/admin", {"is_admin": True, "reason": "r"}),
    ]
    for method, path, body in attempts:
        res = directory.call(admin, method, path, json=body)
        assert res.status_code == 404 and codes(res) == "person_not_found", (method, path)


# ---- reasons ----

def test_clean_reason_trims_and_enforces_the_rules():
    assert audit.clean_reason("  because  ", required=True) == "because"
    assert audit.clean_reason("   ", required=False) is None
    assert audit.clean_reason(None, required=False) is None
    with pytest.raises(AppError) as blank:
        audit.clean_reason("  ", required=True)
    assert blank.value.code == "reason_required"
    with pytest.raises(AppError) as long:
        audit.clean_reason("x" * 501, required=False)
    assert long.value.code == "reason_too_long"
