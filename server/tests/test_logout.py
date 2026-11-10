"""Signing out ends the person's sessions on the server: a token that was stolen or left on a shared screen stops
working at once, instead of living until it expires."""
import pytest

from auth.services import tokens
from core.config import settings


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "k" * 40)


def token_for(person, **extra) -> dict:
    """The header a browser would send after Google sign-in. `ver` is the version the person had when it was issued."""
    claims = {"sub": str(person.id), "ver": 0, **extra}
    return {"Authorization": f"Bearer {tokens.sign('session', claims, 3600)}"}


def test_a_token_works_until_the_person_signs_out_and_never_again_after(directory, npi, db):
    headers = token_for(npi["asha"])
    assert directory.client.get("/api/me", headers=headers).status_code == 200

    out = directory.client.post("/api/auth/logout", headers=headers)

    assert out.status_code == 204
    after = directory.client.get("/api/me", headers=headers)
    assert (after.status_code, after.json()["detail"]["code"]) == (401, "not_authenticated")
    db.expire_all()
    assert npi["asha"].session_version == 1


def test_signing_out_ends_every_token_of_that_person_but_nobody_elses(directory, npi, admin):
    first, second = token_for(npi["asha"]), token_for(npi["asha"])  # two browsers
    admins = token_for(admin)

    directory.client.post("/api/auth/logout", headers=first)

    assert directory.client.get("/api/me", headers=second).status_code == 401  # the other browser is out too
    assert directory.client.get("/api/me", headers=admins).status_code == 200


def test_signing_in_again_gives_a_token_that_works(directory, npi):
    old = token_for(npi["asha"])
    directory.client.post("/api/auth/logout", headers=old)

    fresh = token_for(npi["asha"], ver=1)  # what the next Google sign-in issues: the person's current version

    assert directory.client.get("/api/me", headers=fresh).status_code == 200
    assert directory.client.get("/api/me", headers=old).status_code == 401


def test_a_token_from_before_versions_existed_counts_as_version_0(directory, npi):
    claims = {"sub": str(npi["asha"].id)}  # no `ver` at all
    old_style = {"Authorization": f"Bearer {tokens.sign('session', claims, 3600)}"}

    assert directory.client.get("/api/me", headers=old_style).status_code == 200
    directory.client.post("/api/auth/logout", headers=old_style)
    assert directory.client.get("/api/me", headers=old_style).status_code == 401


def test_a_token_with_a_version_from_the_future_is_refused(directory, npi):
    assert directory.client.get("/api/me", headers=token_for(npi["asha"], ver=5)).status_code == 401


def test_logging_out_with_no_session_is_refused(client):
    assert client.post("/api/auth/logout").status_code == 401
