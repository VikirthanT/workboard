"""Google sign-in end to end, with Google's answers faked so every path can be exercised without the network:
start -> callback -> exchange -> a session token that the rest of the API accepts. Most of the file is refusals:
a sign-in must fail closed, and a failed sign-in must leave nothing behind (no code issued, no session)."""
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

from auth import states
from auth.services import google, login_codes, tokens
from core.config import settings
from core.exceptions import AppError
from models import LoginCode
from tests.conftest import make_team

CLIENT_ID = "test-client.apps.googleusercontent.com"
REDIRECT = "http://localhost:5173/api/auth/google/callback"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """Every test here runs with Google sign-in set up, unless it unsets something itself."""
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(settings, "google_redirect_uri", REDIRECT)
    monkeypatch.setattr(settings, "secret_key", "k" * 40)
    monkeypatch.setattr(settings, "token_ttl_seconds", 3600)


def id_token(real_nonce: str, **over) -> str:
    """An ID token as Google would send it; `over` replaces claims, and None removes one."""
    claims = {
        "iss": "https://accounts.google.com", "aud": CLIENT_ID, "exp": time.time() + 300, "nonce": real_nonce,
        "email": "asha@atimotors.com", "email_verified": True, **over,
    }
    claims = {k: v for k, v in claims.items() if v is not None}  # None removes the claim
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"header.{payload}.signature"


def get(directory, path, **kwargs):
    return directory.call(None, "GET", path, follow_redirects=False, **kwargs)


def start(directory):
    """Press "Continue with Google": the redirect to Google, and the state and nonce it carries."""
    res = get(directory, "/auth/google")
    assert res.status_code == 302, res.text
    query = parse_qs(urlparse(res.headers["location"]).query)
    return res, query["state"][0], query["nonce"][0]


def sign_in(directory, monkeypatch, *, token=None, google_error=None, state=None, cookie=True, **claims):
    """The whole round trip up to and including the callback. Returns the callback's redirect."""
    _, real_state, nonce = start(directory)
    monkeypatch.setattr(google, "exchange_code", lambda _code: token or id_token(nonce, **claims))
    if not cookie:
        directory.client.cookies.clear()
    query = {"error": google_error} if google_error else {"code": "google-code", "state": state or real_state}
    return get(directory, "/auth/google/callback", params=query)


def landed_on(res) -> str:
    assert res.status_code == 302, res.text
    return res.headers["location"]


def one_time_code(res) -> str:
    location = landed_on(res)
    assert location.startswith("/login?code="), location
    return location.removeprefix("/login?code=")


def exchange(directory, code):
    return get(directory, "/auth/google/exchange", params={"code": code})


@pytest.fixture
def asha(db, directory, admin):
    """A manager. The API made her one in its own session, so reload her here or this session keeps the old role."""
    person = directory.person("Asha")
    make_team(directory, admin, "NPI", person)
    db.expire_all()
    return person


# ---- step 1: start ----

def test_start_sends_the_browser_to_google_with_everything_google_needs(directory):
    res, state, nonce = start(directory)

    url = urlparse(res.headers["location"])
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == states.GOOGLE_AUTH_URL
    assert query["client_id"] == [CLIENT_ID] and query["redirect_uri"] == [REDIRECT]
    assert query["response_type"] == ["code"] and query["scope"] == ["openid email profile"]
    assert query["hd"] == ["atimotors.com"]
    assert len(state) >= 24 and len(nonce) >= 24 and state != nonce


def test_each_start_has_its_own_random_state(directory):
    assert start(directory)[1:] != start(directory)[1:]


def test_the_state_cookie_cannot_be_read_by_scripts_and_is_not_sent_cross_site(directory):
    cookie = start(directory)[0].headers["set-cookie"].lower()

    assert states.STATE_COOKIE in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert "path=/api/auth/google" in cookie and "secure" not in cookie  # plain http locally


def test_the_state_cookie_is_secure_when_the_redirect_address_is_https(directory, monkeypatch):
    monkeypatch.setattr(settings, "google_redirect_uri", "https://work.example.com/api/auth/google/callback")

    assert "secure" in start(directory)[0].headers["set-cookie"].lower()


@pytest.mark.parametrize("unset", ["google_client_id", "google_client_secret", "google_redirect_uri", "secret_key"])
def test_without_every_setting_start_goes_back_to_the_login_page_with_an_error(directory, monkeypatch, unset):
    monkeypatch.setattr(settings, unset, "")

    res = get(directory, "/auth/google")

    assert landed_on(res) == "/login?error=oauth_not_configured"


def test_a_secret_key_that_is_too_short_counts_as_not_set(directory, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "short")

    assert landed_on(get(directory, "/auth/google")) == "/login?error=oauth_not_configured"


# ---- steps 2 and 3: the way in ----

def test_a_manager_signs_in_and_the_session_token_works_everywhere(directory, monkeypatch, asha):
    code = one_time_code(sign_in(directory, monkeypatch))

    res = exchange(directory, code)

    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    body = res.json()
    assert (body["email"], body["name"]) == ("asha@atimotors.com", "Asha")
    me = directory.client.get("/api/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200 and me.json()["email"] == "asha@atimotors.com"
    assert directory.client.get("/api/board", headers={"Authorization": f"Bearer {body['token']}"}).status_code == 200


def test_an_admin_can_sign_in_too(directory, admin, monkeypatch):
    code = one_time_code(sign_in(directory, monkeypatch, email="admin@atimotors.com"))

    assert exchange(directory, code).json()["email"] == "admin@atimotors.com"


def test_the_email_is_matched_ignoring_case(directory, monkeypatch, asha):
    code = one_time_code(sign_in(directory, monkeypatch, email="  Asha@AtiMotors.com "))

    assert exchange(directory, code).status_code == 200


def test_the_token_lives_as_long_as_the_setting_says(directory, monkeypatch, asha, db):
    monkeypatch.setattr(settings, "token_ttl_seconds", 120)
    token = exchange(directory, one_time_code(sign_in(directory, monkeypatch))).json()["token"]

    claims = tokens.verify(token, "session")

    assert 115 <= claims["exp"] - time.time() <= 121


def test_the_code_works_once(directory, monkeypatch, asha):
    code = one_time_code(sign_in(directory, monkeypatch))

    first, second = exchange(directory, code), exchange(directory, code)

    assert first.status_code == 200
    assert (second.status_code, second.json()["detail"]["code"]) == (400, "token_exchange_failed")


def test_an_expired_code_is_refused(directory, monkeypatch, asha, db):
    code = one_time_code(sign_in(directory, monkeypatch))
    db.query(LoginCode).update({"expires_at": login_codes.datetime.now(login_codes.timezone.utc) - login_codes.timedelta(seconds=1)})
    db.commit()

    assert exchange(directory, code).status_code == 400


@pytest.mark.parametrize("code", ["nonsense", "x" * 200, "' OR 1=1 --"], ids=["nonsense", "200 characters", "sql injection"])
def test_a_code_that_was_never_issued_is_refused(directory, code):
    res = exchange(directory, code)

    assert (res.status_code, res.json()["detail"]["code"]) == (400, "token_exchange_failed")


def test_a_code_without_a_value_is_422(directory):
    assert directory.call(None, "GET", "/auth/google/exchange", follow_redirects=False).status_code == 422


def test_only_a_hash_of_the_code_is_stored(directory, monkeypatch, asha, db):
    code = one_time_code(sign_in(directory, monkeypatch))

    [row] = db.query(LoginCode).all()

    assert row.code_hash != code and code not in row.code_hash and len(row.code_hash) == 64


def test_a_person_who_lost_their_role_in_the_last_minute_is_refused_at_exchange(directory, monkeypatch, asha, db):
    code = one_time_code(sign_in(directory, monkeypatch))
    asha.active = False
    db.commit()

    res = exchange(directory, code)

    assert (res.status_code, res.json()["detail"]["code"]) == (403, "not_onboarded")


def test_the_state_cookie_is_spent_by_a_successful_sign_in(directory, monkeypatch, asha):
    _, state, nonce = start(directory)
    monkeypatch.setattr(google, "exchange_code", lambda _c: id_token(nonce))
    first = get(directory, "/auth/google/callback", params={"code": "c", "state": state})
    replay = get(directory, "/auth/google/callback", params={"code": "c", "state": state})

    assert landed_on(first).startswith("/login?code=")
    assert landed_on(replay) == "/login?error=invalid_state"


# ---- step 2 refusals: nothing may be issued ----

@pytest.mark.parametrize("kwargs,error", [
    (dict(google_error="access_denied"), "oauth_denied"),
    (dict(cookie=False), "invalid_state"),
    (dict(state="not-the-state"), "invalid_state"),
    (dict(aud="someone-elses-client"), "userinfo_failed"),
    (dict(aud=["a", "b"]), "userinfo_failed"),
    (dict(iss="https://evil.example.com"), "userinfo_failed"),
    (dict(exp=time.time() - 10), "userinfo_failed"),
    (dict(exp="soon"), "userinfo_failed"),
    (dict(nonce="a-nonce-from-another-sign-in"), "userinfo_failed"),
    (dict(email_verified=False), "userinfo_failed"),
    (dict(email_verified="true"), "userinfo_failed"),
    (dict(email=None), "userinfo_failed"),
    (dict(email=42), "userinfo_failed"),
    (dict(token="not-a-token"), "userinfo_failed"),
    (dict(token="a.%%%.c"), "userinfo_failed"),
    (dict(email="someone@gmail.com"), "domain_not_allowed"),
    (dict(email="asha@atimotors.com.evil.com"), "domain_not_allowed"),
    (dict(email="asha@evilatimotors.com"), "domain_not_allowed"),
    (dict(email="ghost@atimotors.com"), "not_onboarded"),
], ids=[
    "cancelled", "no cookie", "wrong state", "wrong audience", "audience list without us", "wrong issuer", "expired",
    "expiry not a number", "wrong nonce", "unverified email", "verified as text", "no email", "email not text",
    "not a token", "undecodable payload", "gmail", "domain as a prefix of another", "domain as a suffix of another", "unknown person",
])
def test_every_refusal_goes_back_to_the_login_page_and_issues_nothing(directory, monkeypatch, asha, db, kwargs, error):
    res = sign_in(directory, monkeypatch, **kwargs)

    assert landed_on(res) == f"/login?error={error}"
    assert db.query(LoginCode).count() == 0


def test_a_callback_with_no_code_is_refused(directory, asha, db):
    _, state, _ = start(directory)

    assert landed_on(get(directory, "/auth/google/callback", params={"state": state})) == "/login?error=invalid_state"
    assert landed_on(get(directory, "/auth/google/callback")) == "/login?error=invalid_state"
    assert db.query(LoginCode).count() == 0


def test_a_callback_with_a_forged_cookie_is_refused(directory, monkeypatch, asha):
    _, state, nonce = start(directory)
    forged = tokens.sign("state", {"state": state, "nonce": nonce}, 600).rsplit(".", 1)[0] + ".forgedsignature"
    directory.client.cookies.set(states.STATE_COOKIE, forged, path="/api/auth/google")
    monkeypatch.setattr(google, "exchange_code", lambda _c: id_token(nonce))

    assert landed_on(get(directory, "/auth/google/callback", params={"code": "c", "state": state})) == "/login?error=invalid_state"


def test_a_session_token_cannot_stand_in_for_the_state_cookie(directory, monkeypatch, asha):
    _, state, nonce = start(directory)
    session = tokens.sign("session", {"sub": str(asha.id), "state": state, "nonce": nonce}, 600)
    directory.client.cookies.set(states.STATE_COOKIE, session, path="/api/auth/google")
    monkeypatch.setattr(google, "exchange_code", lambda _c: id_token(nonce))

    assert landed_on(get(directory, "/auth/google/callback", params={"code": "c", "state": state})) == "/login?error=invalid_state"


def test_google_refusing_the_code_goes_back_with_an_error(directory, monkeypatch, asha, db):
    _, state, _ = start(directory)

    def refuse(_code):
        raise AppError(states.ERR_EXCHANGE, "no", 400)

    monkeypatch.setattr(google, "exchange_code", refuse)

    assert landed_on(get(directory, "/auth/google/callback", params={"code": "c", "state": state})) == "/login?error=token_exchange_failed"
    assert db.query(LoginCode).count() == 0


def test_a_plain_team_member_or_a_person_who_left_cannot_sign_in(directory, monkeypatch, admin, asha, db):
    ravi = directory.person("Ravi")
    directory.call(asha, "POST", f"/teams/{directory.call(admin, 'GET', '/teams').json()[0]['id']}/members", json={"person_id": str(ravi.id)})
    gone = directory.person("Gone", admin=True)
    gone.active = False
    db.commit()

    for email in ("ravi@atimotors.com", "gone@atimotors.com"):
        assert landed_on(sign_in(directory, monkeypatch, email=email)) == "/login?error=not_onboarded", email
    assert db.query(LoginCode).count() == 0


def test_a_person_with_no_team_who_is_not_an_admin_cannot_sign_in(directory, monkeypatch, db):
    directory.person("Loner")

    assert landed_on(sign_in(directory, monkeypatch, email="loner@atimotors.com")) == "/login?error=not_onboarded"


def test_the_callback_without_settings_goes_back_to_login(directory, monkeypatch):
    monkeypatch.setattr(settings, "google_client_secret", "")

    assert landed_on(get(directory, "/auth/google/callback", params={"code": "c", "state": "s"})) == "/login?error=oauth_not_configured"


# ---- the session token, as the rest of the API sees it ----

def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def session_token(person, ttl=3600, **kw):
    return tokens.sign("session", {"sub": str(person.id)}, ttl, **kw)


def test_a_valid_token_signs_the_person_in(directory, asha):
    res = directory.client.get("/api/me", headers=bearer(session_token(asha)))

    assert res.status_code == 200 and res.json()["email"] == "asha@atimotors.com"


def test_the_token_works_with_the_development_sign_in_switched_off(directory, asha, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)

    assert directory.client.get("/api/me", headers=bearer(session_token(asha))).status_code == 200


def test_the_development_header_is_ignored_when_it_is_switched_off(directory, asha, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)

    res = directory.client.get("/api/me", headers={"X-Dev-User-Email": asha.email})

    assert (res.status_code, res.json()["detail"]["code"]) == (401, "not_authenticated")


def test_with_neither_dev_sign_in_nor_google_settings_the_answer_is_501_not_401(directory, asha, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)
    monkeypatch.setattr(settings, "google_client_id", "")

    res = directory.client.get("/api/me")

    assert (res.status_code, res.json()["detail"]["code"]) == (501, "auth_not_configured")


@pytest.mark.parametrize("make", [
    lambda p: session_token(p, now=time.time() - 7200),                       # expired an hour ago
    lambda p: session_token(p)[:-3] + "xyz",                                  # signature altered
    lambda p: "x." + session_token(p).split(".")[1],                           # payload swapped under another signature
    lambda p: "garbage",                                                       # not a token at all
    lambda p: "a.b.c",                                                         # wrong shape
    lambda p: tokens.sign("state", {"sub": str(p.id)}, 3600),                  # a token made for another purpose
    lambda p: tokens.sign("session", {}, 3600),                                # no subject
    lambda p: tokens.sign("session", {"sub": "not-a-uuid"}, 3600),             # a subject that is not an id
    lambda p: tokens.sign("session", {"sub": "00000000-0000-0000-0000-000000000000"}, 3600),  # nobody
], ids=["expired", "altered", "swapped payload", "garbage", "wrong shape", "wrong purpose", "no subject", "bad subject", "unknown person"])
def test_a_bad_token_is_a_401(directory, asha, make):
    res = directory.client.get("/api/me", headers=bearer(make(asha)))

    assert (res.status_code, res.json()["detail"]["code"]) == (401, "not_authenticated")


def test_a_token_signed_with_another_key_is_refused(directory, asha, monkeypatch):
    other = session_token(asha)
    monkeypatch.setattr(settings, "secret_key", "z" * 40)  # the key was changed: everyone is signed out

    assert directory.client.get("/api/me", headers=bearer(other)).status_code == 401


def test_a_token_does_not_outlive_the_role(directory, asha, db):
    token = session_token(asha)
    asha.role = "member"  # no longer a manager
    db.commit()

    res = directory.client.get("/api/me", headers=bearer(token))

    assert (res.status_code, res.json()["detail"]["code"]) == (403, "not_onboarded")


def test_a_token_for_an_inactive_person_is_refused(directory, asha, db):
    token = session_token(asha)
    asha.active = False
    db.commit()

    assert directory.client.get("/api/me", headers=bearer(token)).status_code == 403


def test_the_token_says_nothing_secret(directory, asha):
    payload = session_token(asha).split(".")[0]
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))

    assert set(decoded) == {"sub", "kind", "exp"}  # an id, a purpose and an end time: no email, no role


def test_the_authorization_header_needs_the_bearer_word(directory, asha):
    token = session_token(asha)

    assert directory.client.get("/api/me", headers={"Authorization": f"Basic {token}"}).status_code == 401
    assert directory.client.get("/api/me", headers={"Authorization": token}).status_code == 401  # no scheme word at all
    assert directory.client.get("/api/me", headers={"Authorization": f"bearer {token}"}).status_code == 200  # the word is case-insensitive


# ---- the token module on its own ----

def test_tokens_roundtrip_and_carry_their_data():
    token = tokens.sign("session", {"sub": "abc"}, 60)

    assert tokens.verify(token, "session")["sub"] == "abc"


def test_a_token_is_refused_for_the_wrong_kind_and_after_it_expires():
    token = tokens.sign("session", {"sub": "abc"}, 60, now=1000)

    assert tokens.verify(token, "state", now=1010) is None
    assert tokens.verify(token, "session", now=1059) is not None
    assert tokens.verify(token, "session", now=1060) is None  # the expiry second itself is already too late


def test_signing_refuses_without_a_proper_secret_and_verifying_never_trusts_an_empty_one(monkeypatch):
    good = tokens.sign("session", {"sub": "abc"}, 60)
    monkeypatch.setattr(settings, "secret_key", "")

    with pytest.raises(AppError) as refused:
        tokens.sign("session", {}, 60)
    assert refused.value.status_code == 501
    assert tokens.verify(good, "session") is None


def test_a_tampered_payload_is_refused():
    token = tokens.sign("session", {"sub": "abc"}, 60)
    payload, mac = token.split(".")
    forged = base64.urlsafe_b64encode(json.dumps({"sub": "admin", "kind": "session", "exp": 9999999999}).encode()).rstrip(b"=").decode()

    assert tokens.verify(f"{forged}.{mac}", "session") is None
    assert tokens.verify(f"{payload}.", "session") is None
    assert tokens.verify(payload, "session") is None
