"""Rate limits per login: the counter itself, then each place it is used."""
import pytest

from core.exceptions import AppError
from security import rate_limit


# ---- the counter ----

def test_calls_up_to_the_limit_pass_and_the_next_is_a_429_with_a_retry_hint():
    for second in range(3):
        rate_limit.check(("k",), 3, 60, now=second)

    with pytest.raises(AppError) as err:
        rate_limit.check(("k",), 3, 60, now=3)

    assert (err.value.status_code, err.value.code) == (429, "rate_limited")
    assert err.value.headers == {"Retry-After": "58"}  # the oldest call (second 0) leaves the 60 s window at second 60


def test_the_window_slides_so_old_calls_stop_counting():
    for second in range(3):
        rate_limit.check(("k",), 3, 60, now=second)

    rate_limit.check(("k",), 3, 60, now=60.5)  # only the call from second 0 has left the window: room for exactly one

    with pytest.raises(AppError):
        rate_limit.check(("k",), 3, 60, now=60.6)


def test_each_key_has_its_own_budget():
    rate_limit.check(("a",), 1, 60, now=0)
    rate_limit.check(("b",), 1, 60, now=0)

    with pytest.raises(AppError):
        rate_limit.check(("a",), 1, 60, now=1)


def test_a_huge_table_is_trimmed_of_idle_keys(monkeypatch):
    monkeypatch.setattr(rate_limit, "_MAX_KEYS", 5)
    for n in range(6):
        rate_limit.check(("old", n), 1, 60, now=0)

    rate_limit.check(("new",), 1, 60, now=10_000)  # past the idle horizon: the six old keys are dropped

    assert list(rate_limit._calls) == [("new",)]


# ---- every protected endpoint counts against the signed-in person ----

def test_one_person_cannot_exceed_the_api_budget_but_others_are_unaffected(directory, npi, monkeypatch):
    monkeypatch.setattr(rate_limit, "API_PER_MINUTE", 3)
    rate_limit.reset()  # the npi fixture already made a call as Asha

    codes = [directory.call(npi["asha"], "GET", "/me").status_code for _ in range(5)]
    other = directory.call(npi["zoe"], "GET", "/me")  # a plain member: refused as not onboarded, not as rate limited

    assert codes == [200, 200, 200, 429, 429]
    assert other.status_code == 403
    blocked = directory.call(npi["asha"], "GET", "/me")
    assert (blocked.json()["detail"]["code"], blocked.headers["retry-after"].isdigit()) == ("rate_limited", True)


def test_a_request_with_no_session_does_not_use_up_anyones_budget(directory, npi, client, monkeypatch):
    monkeypatch.setattr(rate_limit, "API_PER_MINUTE", 2)
    for _ in range(10):
        assert client.get("/api/me").status_code == 401

    assert directory.call(npi["asha"], "GET", "/me").status_code == 200


def test_the_bulk_upload_has_its_own_smaller_budget(directory, npi, monkeypatch):
    monkeypatch.setattr(rate_limit, "IMPORT_PER_MINUTE", 2)
    files = {"file": ("x.xlsx", b"junk", "application/octet-stream")}

    codes = [directory.call(npi["asha"], "POST", "/tasks/import", files=files).status_code for _ in range(3)]

    assert codes == [422, 422, 429]  # two rejected files (not a spreadsheet), then the budget is spent
    assert directory.call(npi["asha"], "GET", "/me").status_code == 200  # the rest of the API is not affected

# The per-email sign-in limit is tested in test_google_auth.py, next to the sign-in helpers it needs.
