"""Two people changing the same thing at the same moment. The services lock the rows they check, so a race has one
winner and one clean refusal, never two successes and never a 500. Each race is run several times, because a missing
lock shows up only some of the time; with the locks in place the outcome is the same every time."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from main import app
from tests.conftest import make_team

ROUNDS = 6


def race(*calls):
    """Run each (who, method, path, body) at the same moment, one thread and one client each; the status codes."""
    start = Barrier(len(calls))

    def go(call):
        who, method, path, body = call
        with TestClient(app) as client:
            start.wait()
            return client.request(method, f"/api{path}", headers={"X-Dev-User-Email": who.email}, json=body).status_code

    with ThreadPoolExecutor(len(calls)) as pool:
        return sorted(pool.map(go, calls))


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_one_person_added_to_two_teams_at_once_lands_on_exactly_one(directory, admin, db, round_):
    one = make_team(directory, admin, "One", directory.person(f"Ann{round_}"))
    two = make_team(directory, admin, "Two", directory.person(f"Bob{round_}"))
    zoe = directory.person(f"Zoe{round_}")
    add = lambda team: (admin, "POST", f"/teams/{team['id']}/members", {"person_id": str(zoe.id), "reason": "joins"})

    assert race(add(one), add(two)) == [201, 409]

    db.refresh(zoe)
    assert zoe.team_id is not None
    added = directory.call(admin, "GET", "/audit-log?limit=200").json()["items"]
    assert [e["action"] for e in added if e["person_name"] == zoe.name] == ["member.add"]  # one change, one audit row


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_one_person_made_manager_of_two_teams_at_once_manages_exactly_one(directory, admin, db, round_):
    one = make_team(directory, admin, "One", directory.person(f"Ann{round_}"))
    two = make_team(directory, admin, "Two", directory.person(f"Bob{round_}"))
    zoe = directory.person(f"Zoe{round_}")
    directory.call(admin, "POST", f"/teams/{one['id']}/members", json={"person_id": str(zoe.id), "reason": "joins"})
    promote = lambda team: (admin, "PATCH", f"/teams/{team['id']}/manager", {"person_id": str(zoe.id), "reason": "cover"})

    statuses = race(promote(one), promote(two))

    assert statuses[0] == 200 and statuses[1] in (404, 409, 422)  # the other team lost (she is on One, not Two)
    teams = directory.call(admin, "GET", "/teams").json()
    assert [t["name"] for t in teams if t["manager"] and t["manager"]["id"] == str(zoe.id)] == ["One"]


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_two_admins_revoking_each_other_at_once_leave_one_admin(directory, db, round_):
    first = directory.person(f"First{round_}", admin=True)
    second = directory.person(f"Second{round_}", admin=True)
    revoke = lambda by, target: (by, "PATCH", f"/people/{target.id}/admin", {"is_admin": False, "reason": "swap"})

    # Before the lock order was fixed this deadlocked in Postgres and one request died with a 500.
    assert race(revoke(first, second), revoke(second, first)) == [200, 409]  # the loser gets `last_admin`

    db.expire_all()
    assert [p.is_admin for p in (first, second)].count(True) == 1
