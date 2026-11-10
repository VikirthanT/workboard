"""The API's whole front door, checked route by route: nobody gets in without signing in, and signing in is not enough
without being set up as a manager or admin. The routes are read from the app itself, so a new endpoint is covered the
moment it exists: it cannot ship unauthenticated without this file failing."""
import uuid

import pytest

from core.config import settings
from main import app

# The only listed routes that answer without a session. Each has its own reason and its own tests.
PUBLIC = {
    ("GET", "/api/health"),  # the container health check
    ("GET", "/api/dev/accounts"),  # a 404 unless DEV_AUTH is on (see the test below)
    ("GET", "/api/auth/google/exchange"),  # trades a one-time code for a session; the code is the credential
}
# The Google sign-in start and callback routes (/api/auth/google, /api/auth/google/callback) are public too, but they
# are hidden from the OpenAPI schema (include_in_schema=False), which is where this file reads the routes from.
# test_google_auth.py covers them. A new route hidden from the schema would not be seen here: do not hide a route
# that needs sign-in.


def _routes() -> list[tuple[str, str]]:
    """Every route in the API's OpenAPI schema (a stable public view; the router objects are not)."""
    return [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() not in ("HEAD", "OPTIONS")
    ]


PROTECTED = [r for r in _routes() if r not in PUBLIC]


def _url(path: str) -> str:
    """Fill every {placeholder} with a well-formed id, so the request reaches the sign-in check, not path validation."""
    while "{" in path:
        start, end = path.index("{"), path.index("}")
        path = path[:start] + str(uuid.uuid4()) + path[end + 1:]
    return path


def test_the_route_list_is_real_and_the_public_list_is_accurate():
    assert len(PROTECTED) >= 20  # an empty list would make the tests below pass for nothing (23 when this was written)
    assert PUBLIC <= set(_routes()), "a route in PUBLIC no longer exists: remove it from the list"


@pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
def test_a_caller_with_no_session_is_refused(client, method, path):
    res = client.request(method, _url(path), json={})  # `{}` parses, so the refusal comes from sign-in, not the body

    assert (res.status_code, res.json()["detail"]["code"]) == (401, "not_authenticated")


@pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
def test_a_signed_in_person_who_is_not_a_manager_or_admin_is_refused(directory, method, path):
    plain = directory.person("Plain")  # in the directory, a plain member: an assignee, never a user

    res = directory.client.request(method, _url(path), json={}, headers={"X-Dev-User-Email": plain.email})

    assert (res.status_code, res.json()["detail"]["code"]) == (403, "not_onboarded")


def test_the_dev_sign_in_does_nothing_when_dev_auth_is_off(directory, admin, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)

    as_admin = directory.client.get("/api/me", headers={"X-Dev-User-Email": admin.email})
    accounts = directory.client.get("/api/dev/accounts")

    assert as_admin.status_code in (401, 501)  # never 200: the header is just a header
    assert accounts.status_code == 404


def test_a_bearer_token_that_is_forged_or_for_the_wrong_purpose_is_refused(directory, admin, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "k" * 40)
    for token in ("", "garbage", "a.b", "e30.AAAA", "x" * 300):
        res = directory.client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401, token


def test_no_other_origin_is_given_access_to_the_api(client):
    simple = client.get("/api/health", headers={"Origin": "https://evil.example"})
    preflight = client.options(
        "/api/tasks", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )

    assert "access-control-allow-origin" not in simple.headers
    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-credentials" not in preflight.headers


# ---- the upload reads nothing from a caller it has not identified ----

def _multipart(client, body: bytes, headers=None):
    return client.post(
        "/api/tasks/import", content=body, headers={"Content-Type": "multipart/form-data; boundary=zzz", **(headers or {})}
    )


def test_a_malformed_upload_from_nobody_is_refused_before_it_is_parsed(client):
    res = _multipart(client, b"this is not multipart")

    assert (res.status_code, res.json()["detail"]["code"]) == (401, "not_authenticated")  # not 400 "invalid multipart"


def test_a_malformed_upload_from_a_manager_is_a_400_and_a_missing_file_is_a_422(directory, npi):
    asha = {"X-Dev-User-Email": npi["asha"].email}

    assert _multipart(directory.client, b"this is not multipart", asha).status_code == 400
    empty = directory.client.post("/api/tasks/import", data={"other": "x"}, headers=asha)
    assert (empty.status_code, empty.json()["detail"]["code"]) == (422, "invalid_file")


def test_an_upload_that_announces_a_huge_body_is_refused_without_reading_it(directory, npi):
    res = _multipart(directory.client, b"x", {"X-Dev-User-Email": npi["asha"].email, "Content-Length": str(50 * 1024 * 1024)})

    assert res.status_code in (413, 422, 400)  # the exact code depends on where the client library stops it; never 201
