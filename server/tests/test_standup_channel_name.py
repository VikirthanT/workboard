"""Looking up a channel's name from its id, for the team page: the standup app's channel list first, then Slack.
Both are faked at their edge."""
import pytest
from sqlalchemy.exc import OperationalError

from core.config import settings
from core.exceptions import AppError
from slack import client
from standups.standup_db import reader
from tests.conftest import make_team


@pytest.fixture
def world(directory, admin, monkeypatch):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    make_team(directory, admin, "NPI", asha)
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(reader, "list_channels", lambda: [])  # the standup app lists nothing unless a test says so
    monkeypatch.setattr(client, "channel_name", lambda token, channel: "npi-standup")
    return {"d": directory, "admin": admin, "asha": asha, "ravi": ravi}


def lookup(world, who, channel="C0NPI"):
    return world["d"].call(who, "GET", f"/standups/channels/{channel}")


def test_an_admin_or_a_manager_gets_the_name_of_the_channel(world):
    for who in (world["admin"], world["asha"]):
        res = lookup(world, who)
        assert res.status_code == 200 and res.json() == {"id": "C0NPI", "name": "npi-standup"}


def test_the_standup_apps_own_list_answers_first_and_slack_is_not_asked(world, monkeypatch):
    def boom(token, channel):
        raise AssertionError("Slack must not be asked for a channel the standup app lists")
    monkeypatch.setattr(reader, "list_channels", lambda: [reader.Channel("C0NPI", "standup-npi")])
    monkeypatch.setattr(client, "channel_name", boom)

    assert lookup(world, world["asha"]).json() == {"id": "C0NPI", "name": "standup-npi"}


def test_it_works_from_the_standup_app_alone_and_says_so_when_it_does_not_know_the_id(world, monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", "")  # no Slack
    monkeypatch.setattr(reader, "list_channels", lambda: [reader.Channel("C0NPI", "standup-npi")])

    assert lookup(world, world["asha"]).json()["name"] == "standup-npi"
    unknown = lookup(world, world["asha"], "C0OTHER")
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (404, "channel_not_found")


def test_an_unreadable_standup_database_falls_back_to_slack(world, monkeypatch):
    def unreadable():
        raise OperationalError("select", {}, Exception("unable to open database file"))
    monkeypatch.setattr(reader, "list_channels", unreadable)
    assert lookup(world, world["asha"]).json()["name"] == "npi-standup"

    def not_set_up():
        raise AppError("standups_not_configured", "No standup database.", 501)
    monkeypatch.setattr(reader, "list_channels", not_set_up)
    assert lookup(world, world["asha"]).json()["name"] == "npi-standup"


def test_channel_name_lookups_share_the_twenty_a_minute_budget_for_asking_slack(world):
    from security import rate_limit

    codes = [lookup(world, world["asha"]).status_code for _ in range(rate_limit.SLACK_READ_PER_MINUTE + 1)]

    assert codes == [200] * rate_limit.SLACK_READ_PER_MINUTE + [429]
    assert lookup(world, world["admin"]).status_code == 200


def test_nobody_else_may_ask(world):
    assert lookup(world, None).status_code == 401
    assert lookup(world, world["ravi"]).status_code == 403  # a plain member


def test_it_says_why_when_the_channel_cannot_be_found(world, monkeypatch):
    def refuse(code):
        def fake(token, channel):
            raise client.SlackError(f"Slack refused it: {code}.")
        return fake

    for code, status, expected in (("channel_not_found", 404, "channel_not_found"), ("not_in_channel", 409, "bot_not_in_channel"), ("fatal_error", 502, "slack_failed")):
        monkeypatch.setattr(client, "channel_name", refuse(code))
        res = lookup(world, world["asha"])
        assert (res.status_code, res.json()["detail"]["code"]) == (status, expected), code

    monkeypatch.setattr(settings, "slack_bot_token", "")
    monkeypatch.setattr(reader, "list_channels", lambda: (_ for _ in ()).throw(AppError("standups_not_configured", "x", 501)))
    assert lookup(world, world["asha"]).json()["detail"]["code"] == "slack_not_configured"  # nothing to ask at all


def test_an_id_that_is_not_letters_and_digits_is_refused_before_anything_is_asked(world, monkeypatch):
    def boom(*args):
        raise AssertionError("nothing may be asked about a malformed id")
    monkeypatch.setattr(client, "channel_name", boom)
    monkeypatch.setattr(reader, "list_channels", boom)

    for bad in ("ab", "C0%20NPI", "C0-NPI", "C" * 33):
        assert lookup(world, world["asha"], bad).status_code == 422, bad
