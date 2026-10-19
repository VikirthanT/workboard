"""Text the API must store as given or refuse cleanly, never crash on: non-ASCII, emoji, and the NUL character
(which Postgres text columns cannot hold, so it must be caught before the database sees it)."""
import pytest

from tests.conftest import make_team

NUL = "\u0000"
UNICODE = "Überprüfung 日本語 العربية 😀 é"  # accents, CJK, right-to-left, emoji, a combining accent


def task(directory, npi, **fields):
    return directory.call(npi["asha"], "POST", "/tasks", json={"title": "t", "assignee_id": str(npi["ravi"].id), **fields})


def test_non_ascii_text_is_stored_and_returned_exactly(directory, admin, npi):
    made = task(directory, npi, title=UNICODE, description=UNICODE)
    assert made.status_code == 201
    tid = made.json()["id"]
    comment = directory.call(npi["asha"], "POST", f"/tasks/{tid}/comments", json={"body": UNICODE})
    assert comment.status_code == 201 and comment.json()["note"] == UNICODE

    detail = directory.call(npi["asha"], "GET", f"/tasks/{tid}").json()
    assert detail["task"]["title"] == UNICODE and detail["task"]["description"] == UNICODE
    assert [e["note"] for e in detail["timeline"] if e["kind"] == "comment"] == [UNICODE]


def test_non_ascii_team_names_reasons_and_search_work(directory, admin):
    lee = directory.person("Lee", email="lee@atimotors.com")
    team = directory.call(admin, "POST", "/teams", json={"name": UNICODE, "initial_manager_person_id": str(lee.id), "reason": UNICODE})
    assert team.status_code == 201 and team.json()["name"] == UNICODE
    entry = directory.call(admin, "GET", "/audit-log").json()["items"][0]
    assert entry["reason"] == UNICODE and entry["team_name"] == UNICODE
    assert directory.call(admin, "GET", "/people?q=%E6%97%A5").status_code == 200  # a non-ASCII query is fine


def test_the_length_limits_count_characters_not_bytes(directory, npi):
    assert task(directory, npi, title="😀" * 140).status_code == 201  # 140 characters, 560 bytes
    assert task(directory, npi, title="😀" * 141).status_code == 422


def test_text_the_database_cannot_hold_is_a_422_not_a_500(directory, admin, npi):
    tid = task(directory, npi).json()["id"]
    lee = directory.person("Lee")
    attempts = [
        ("task title", directory.call(npi["asha"], "POST", "/tasks", json={"title": f"a{NUL}b", "assignee_id": str(npi["ravi"].id)})),
        ("task description", task(directory, npi, description=f"a{NUL}b")),
        ("task edit", directory.call(npi["asha"], "PATCH", f"/tasks/{tid}", json={"title": f"a{NUL}b"})),
        ("comment", directory.call(npi["asha"], "POST", f"/tasks/{tid}/comments", json={"body": f"a{NUL}b"})),
        ("move note", directory.call(npi["asha"], "POST", f"/tasks/{tid}/status", json={"to": "blocked", "note": f"a{NUL}b"})),
        ("team name", directory.call(admin, "POST", "/teams", json={"name": f"a{NUL}b", "initial_manager_person_id": str(lee.id), "reason": "r"})),
        ("team reason", directory.call(admin, "POST", "/teams", json={"name": "QA", "initial_manager_person_id": str(lee.id), "reason": f"a{NUL}b"})),
        ("member reason", directory.call(admin, "POST", f"/teams/{npi['team']['id']}/members", json={"person_id": str(npi["zoe"].id), "reason": f"a{NUL}b"})),
        ("search", directory.call(admin, "GET", "/people?q=a%00b")),
    ]

    assert {name: res.status_code for name, res in attempts} == {name: 422 for name, _ in attempts}


def test_a_refused_nul_changes_nothing(directory, admin, npi):
    before = directory.call(admin, "GET", "/audit-log").json()["total"]
    tid = task(directory, npi).json()["id"]
    directory.call(npi["asha"], "POST", f"/tasks/{tid}/comments", json={"body": f"a{NUL}b"})
    directory.call(admin, "POST", f"/teams/{npi['team']['id']}/members", json={"person_id": str(npi["zoe"].id), "reason": f"a{NUL}b"})

    assert [e["kind"] for e in directory.call(npi["asha"], "GET", f"/tasks/{tid}").json()["timeline"]] == ["created"]
    assert directory.call(admin, "GET", "/audit-log").json()["total"] == before
