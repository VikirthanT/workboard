"""The application shell: health check, settings, and what an unexpected failure looks like from outside."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.config import Settings, settings
from identity.services import teams
from main import app
from tests.conftest import make_team


def test_health_needs_no_sign_in(client):
    res = client.get("/api/health")
    assert res.status_code == 200 and res.json() == {"status": "ok"}


def test_health_stays_open_even_when_sign_in_is_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "dev_auth", False)
    assert client.get("/api/health").status_code == 200


# ---- settings ----

def test_bootstrap_admin_emails_are_split_trimmed_and_lowercased():
    parsed = Settings(bootstrap_admin_emails=" First@Ati.com, ,second@ati.com ,").admin_emails
    assert parsed == ["first@ati.com", "second@ati.com"]
    assert Settings(bootstrap_admin_emails="").admin_emails == []


def test_dev_auth_is_off_unless_explicitly_turned_on(monkeypatch):
    monkeypatch.delenv("DEV_AUTH", raising=False)
    assert Settings().dev_auth is False
    for value, expected in (("true", True), ("1", True), ("false", False), ("0", False)):
        monkeypatch.setenv("DEV_AUTH", value)
        assert Settings().dev_auth is expected, value


def test_the_database_url_has_no_default_so_no_credentials_live_in_the_code(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings()


def test_a_plain_postgresql_url_gets_the_installed_driver(monkeypatch):
    for given, expected in (
        ("postgresql://u:p@db:5432/app", "postgresql+psycopg://u:p@db:5432/app"),
        ("postgres://u:p@db:5432/app", "postgresql+psycopg://u:p@db:5432/app"),
        ("postgresql+psycopg://u:p@db:5432/app", "postgresql+psycopg://u:p@db:5432/app"),
    ):
        monkeypatch.setenv("DATABASE_URL", given)
        assert Settings().database_url == expected, given


def test_the_other_settings_default_to_the_company_domain_and_no_bootstrap_admins(monkeypatch):
    for name in ("ALLOWED_EMAIL_DOMAIN", "BOOTSTRAP_ADMIN_EMAILS"):
        monkeypatch.delenv(name, raising=False)
    fresh = Settings()
    assert fresh.allowed_email_domain == "atimotors.com" and fresh.admin_emails == []


def test_the_allowed_domain_comes_from_settings_not_from_the_code(directory, admin, monkeypatch):
    asha = directory.person("Asha")
    make_team(directory, admin, "NPI", asha)
    assert directory.call(asha, "GET", "/me").status_code == 200

    monkeypatch.setattr(settings, "allowed_email_domain", "example.org")

    res = directory.call(asha, "GET", "/me")
    assert res.status_code == 403 and res.json()["detail"]["code"] == "domain_not_allowed"


# ---- an unexpected failure ----

def test_an_unexpected_error_is_a_plain_500_that_leaks_nothing(directory, admin, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("secret detail: password=hunter2")

    monkeypatch.setattr(teams, "list_teams", explode)
    quiet = TestClient(app, raise_server_exceptions=False)  # behave like a real server, not like a test

    res = quiet.get("/api/teams", headers={"X-Dev-User-Email": admin.email})

    assert res.status_code == 500
    assert "secret" not in res.text and "hunter2" not in res.text and "RuntimeError" not in res.text


@pytest.mark.parametrize("path", ["/api/nope", "/teams", "/api/teams/extra/segments/here"])
def test_unknown_routes_are_a_404(client, path):
    assert client.get(path).status_code == 404
