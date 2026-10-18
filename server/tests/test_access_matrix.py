"""Every endpoint against every kind of caller, so a missing permission check shows up as a failing row.

Callers: nobody (no identity), a plain member (cannot sign in), a manager of another team, the team's own
manager, and an admin. Each case runs in a fresh world, because several of them change data.
"""
import json
from string import Template

import pytest

from tests.conftest import make_team

ACTORS = ["anon", "member", "other_manager", "own_manager", "admin"]


@pytest.fixture
def world(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    npi = make_team(directory, admin, "NPI", asha)
    make_team(directory, admin, "QA", ravi)
    meena, loner = directory.person("Meena"), directory.person("Loner")
    directory.call(asha, "POST", f"/teams/{npi['id']}/members", json={"person_id": str(meena.id)})
    return {
        "actors": {"anon": None, "member": meena, "other_manager": ravi, "own_manager": asha, "admin": admin},
        "ids": {"npi": npi["id"], "meena": str(meena.id), "loner": str(loner.id)},
    }


# (label, method, path, body, expected status per actor). Paths and bodies use $npi, $meena, $loner.
CASES = [
    ("me", "GET", "/me", None,
     dict(anon=401, member=403, other_manager=200, own_manager=200, admin=200)),
    ("people", "GET", "/people", None,
     dict(anon=401, member=403, other_manager=200, own_manager=200, admin=200)),
    ("list teams", "GET", "/teams", None,
     dict(anon=401, member=403, other_manager=200, own_manager=200, admin=200)),
    ("create team", "POST", "/teams", '{"name": "Mech", "initial_manager_person_id": "$loner", "reason": "r"}',
     dict(anon=401, member=403, other_manager=403, own_manager=403, admin=201)),
    ("delete team", "DELETE", "/teams/$npi", '{"confirm_name": "NPI", "reason": "r"}',
     dict(anon=401, member=403, other_manager=403, own_manager=403, admin=204)),
    ("change manager", "PATCH", "/teams/$npi/manager", '{"person_id": "$meena", "reason": "r"}',
     dict(anon=401, member=403, other_manager=403, own_manager=403, admin=200)),
    ("list members", "GET", "/teams/$npi/members", None,
     dict(anon=401, member=403, other_manager=403, own_manager=200, admin=200)),
    ("add member", "POST", "/teams/$npi/members", '{"person_id": "$loner", "reason": "r"}',
     dict(anon=401, member=403, other_manager=403, own_manager=201, admin=201)),
    ("remove member", "DELETE", "/teams/$npi/members/$meena", '{"reason": "r"}',
     dict(anon=401, member=403, other_manager=403, own_manager=204, admin=204)),
    ("toggle admin", "PATCH", "/people/$loner/admin", '{"is_admin": true, "reason": "r"}',
     dict(anon=401, member=403, other_manager=403, own_manager=403, admin=200)),
    ("audit log", "GET", "/audit-log", None,
     dict(anon=401, member=403, other_manager=403, own_manager=403, admin=200)),
]


@pytest.mark.parametrize("actor", ACTORS)
@pytest.mark.parametrize("label,method,path,body,expected", CASES, ids=[case[0] for case in CASES])
def test_who_may_call_what(directory, world, label, method, path, body, expected, actor):
    ids = world["ids"]
    kwargs = {"json": json.loads(Template(body).substitute(ids))} if body else {}

    res = directory.call(world["actors"][actor], method, Template(path).substitute(ids), **kwargs)

    assert res.status_code == expected[actor], res.text
    if res.status_code >= 400:
        code = res.json()["detail"]["code"]
        # 401 means no identity; a member is not onboarded; a manager acting outside their team is forbidden.
        assert code == {"anon": "not_authenticated", "member": "not_onboarded"}.get(actor, "forbidden")
