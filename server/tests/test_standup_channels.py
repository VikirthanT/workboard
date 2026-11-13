"""GET /standups/channels: the admin's channel picker. The reader itself is tested in test_standup_reader.py."""
import pytest

from standups.standup_db import reader
from tests.conftest import make_team


@pytest.fixture
def two_channels(monkeypatch):
    monkeypatch.setattr(
        reader, "list_channels", lambda: [reader.Channel("C0NPI", "standup-npi"), reader.Channel("C0QA", "standup-qa")]
    )


def test_an_admin_gets_the_channels(directory, admin, two_channels):
    res = directory.call(admin, "GET", "/standups/channels")

    assert res.status_code == 200
    assert res.json() == [
        {"slack_channel_id": "C0NPI", "name": "standup-npi"},
        {"slack_channel_id": "C0QA", "name": "standup-qa"},
    ]


def test_nobody_else_gets_them(directory, admin, two_channels):
    asha, meena = directory.person("Asha"), directory.person("Meena")
    make_team(directory, admin, "NPI", asha)

    assert directory.call(None, "GET", "/standups/channels").status_code == 401
    assert directory.call(asha, "GET", "/standups/channels").status_code == 403  # a manager, not an admin
    assert directory.call(meena, "GET", "/standups/channels").status_code == 403  # a plain member


def test_without_a_standup_database_it_says_so(directory, admin):
    res = directory.call(admin, "GET", "/standups/channels")

    assert res.status_code == 501
    assert res.json()["detail"]["code"] == "standups_not_configured"
