"""`google.exchange_code`: the one call that goes to Google's token endpoint. The other Google tests replace this
function, so its own handling of Google's answers is tested here with `httpx.post` faked. Nothing is sent anywhere."""
import logging

import httpx
import pytest

from auth import states
from auth.services import google
from core.config import settings
from core.exceptions import AppError


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret-value")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:5173/api/auth/google/callback")


def fake_post(monkeypatch, response=None, raises=None):
    sent = {}

    def post(url, data, timeout):
        sent.update(url=url, data=data, timeout=timeout)
        if raises:
            raise raises
        return response

    monkeypatch.setattr(google.httpx, "post", post)
    return sent


def refused(code="abc"):
    with pytest.raises(AppError) as err:
        google.exchange_code(code)
    assert (err.value.code, err.value.status_code) == (states.ERR_EXCHANGE, 400)


def test_a_good_answer_returns_the_id_token_and_sends_what_google_needs(monkeypatch):
    sent = fake_post(monkeypatch, httpx.Response(200, json={"id_token": "the.id.token"}))

    assert google.exchange_code("abc") == "the.id.token"
    assert sent["url"] == states.GOOGLE_TOKEN_URL
    assert sent["data"] == {
        "code": "abc", "client_id": settings.google_client_id, "client_secret": "test-secret-value",
        "redirect_uri": settings.google_redirect_uri, "grant_type": "authorization_code",
    }
    assert sent["timeout"] == 10  # a slow Google must not hang the sign-in


def test_google_refusing_the_code_is_refused_and_logged_without_the_secret(monkeypatch, caplog):
    fake_post(monkeypatch, httpx.Response(400, json={"error": "invalid_grant", "error_description": "Bad Request"}))
    monkeypatch.setattr(google.log, "disabled", False)  # the suite's Alembic run (fileConfig) switches existing loggers off

    with caplog.at_level(logging.WARNING):
        refused()
    assert "invalid_grant" in caplog.text
    assert "test-secret-value" not in caplog.text


@pytest.mark.parametrize("body", [{}, {"id_token": None}, {"id_token": 123}, {"id_token": ["x"]}])
def test_an_answer_without_a_text_id_token_is_refused(monkeypatch, body):
    fake_post(monkeypatch, httpx.Response(200, json=body))

    refused()


def test_an_answer_that_is_not_json_is_refused(monkeypatch):
    fake_post(monkeypatch, httpx.Response(200, text="<html>bad gateway</html>"))

    refused()


@pytest.mark.parametrize("problem", [httpx.ConnectError("down"), httpx.ReadTimeout("slow")])
def test_google_being_unreachable_is_refused_as_a_failed_exchange(monkeypatch, problem):
    fake_post(monkeypatch, raises=problem)

    refused()
