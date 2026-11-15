"""Pulling a team's Slack channel members into the team: the review list (GET) and the all-or-nothing add (POST).
Slack is faked at its edge; the people are made up."""
import pytest
from sqlalchemy import select

from core.config import settings
from models import AccessAuditLog, Team
from slack import client
from tests.conftest import make_team


@pytest.fixture
def world(directory, admin, monkeypatch):
    asha, ravi, meena, omar, zoe = (directory.person(n) for n in ("Asha", "Ravi", "Meena", "Omar", "Zoe"))
    npi = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{npi['id']}/members", json={"person_id": str(ravi.id)})
    qa = make_team(directory, admin, "QA", zoe)
    in_channel = [asha.slack_user_id, ravi.slack_user_id, meena.slack_user_id, omar.slack_user_id, zoe.slack_user_id, "UBOT00001"]
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(client, "channel_member_ids", lambda token, channel: in_channel)
    return {"d": directory, "admin": admin, "asha": asha, "ravi": ravi, "meena": meena, "omar": omar, "zoe": zoe, "npi": npi, "qa": qa}


def pull(world, who, team="npi"):
    return world["d"].call(who, "GET", f"/teams/{world[team]['id']}/channel-members")


def add(world, who, people, team="npi", **extra):
    ids = [str(world[p].id) for p in people]
    return world["d"].call(who, "POST", f"/teams/{world[team]['id']}/members/bulk", json={"person_ids": ids, **extra})


def test_each_person_in_the_channel_says_what_adding_them_would_do(world):
    res = pull(world, world["asha"])

    assert res.status_code == 200
    body = res.json()
    assert body["channel_id"] == "C0TEST" and body["not_in_directory"] == 1  # the bot is not in the directory
    states = {m["person"]["name"]: (m["state"], m["team_name"]) for m in body["members"]}
    assert states == {
        "Asha": ("on_this_team", None), "Ravi": ("on_this_team", None), "Meena": ("available", None),
        "Omar": ("available", None), "Zoe": ("on_other_team", "QA"),
    }
    assert [m["person"]["name"] for m in body["members"]] == sorted(states)  # by name


def test_an_inactive_person_and_a_manager_with_no_team_are_unavailable(world, db):
    world["meena"].active = False
    world["omar"].role = "manager"
    db.commit()

    states = {m["person"]["name"]: m["state"] for m in pull(world, world["asha"]).json()["members"]}

    assert states["Meena"] == "unavailable" and states["Omar"] == "unavailable"


def test_only_that_teams_manager_or_an_admin_may_pull_or_add(world):
    assert pull(world, None).status_code == 401
    assert pull(world, world["zoe"]).status_code == 403  # another team's manager
    assert pull(world, world["ravi"]).status_code == 403  # a plain member
    assert pull(world, world["admin"]).status_code == 200  # any team
    assert pull(world, world["zoe"], team="qa").status_code == 200  # their own

    assert add(world, world["zoe"], ["meena"]).status_code == 403
    assert add(world, world["ravi"], ["meena"]).status_code == 403
    assert add(world, None, ["meena"]).status_code == 401
    assert add(world, world["admin"], ["meena"]).status_code == 201


def test_the_page_says_why_when_the_channel_cannot_be_read(world, db, monkeypatch):
    def refuse(code):
        def fake(token, channel):
            raise client.SlackError(f"Slack refused it: {code}.")
        return fake

    for code, status, expected in (("channel_not_found", 404, "channel_not_found"), ("not_in_channel", 409, "bot_not_in_channel"), ("ratelimited", 502, "slack_failed")):
        monkeypatch.setattr(client, "channel_member_ids", refuse(code))
        res = pull(world, world["asha"])
        assert (res.status_code, res.json()["detail"]["code"]) == (status, expected), code

    monkeypatch.setattr(settings, "slack_bot_token", "")
    assert pull(world, world["asha"]).json()["detail"]["code"] == "slack_not_configured"

    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    db.get(Team, world["npi"]["id"]).standup_channel_id = None
    db.commit()
    res = pull(world, world["asha"])
    assert (res.status_code, res.json()["detail"]["code"]) == (409, "standup_channel_not_set")


def test_asking_slack_for_a_channels_members_is_limited_to_twenty_a_minute(world):
    from security import rate_limit

    assert rate_limit.SLACK_READ_PER_MINUTE == 20

    codes = [pull(world, world["asha"]).status_code for _ in range(21)]

    assert codes == [200] * 20 + [429]
    assert pull(world, world["admin"]).status_code == 200  # another person has their own budget
    assert world["d"].call(world["asha"], "GET", "/me").status_code == 200  # and the rest of the API is not affected


def test_the_ticked_people_are_added_together_and_each_is_audited(world, db):
    res = add(world, world["asha"], ["meena", "omar"], reason="from the channel")

    assert res.status_code == 201 and {p["name"] for p in res.json()} == {"Meena", "Omar"}
    assert {p["team_name"] for p in res.json()} == {"NPI"}
    rows = list(db.scalars(select(AccessAuditLog).where(AccessAuditLog.action == "member.add", AccessAuditLog.person_id.in_([world["meena"].id, world["omar"].id]))))
    assert len(rows) == 2 and {r.reason for r in rows} == {"from the channel"}


def test_one_person_who_cannot_be_added_means_nobody_is(world, db):
    res = add(world, world["asha"], ["meena", "zoe"])  # Zoe already runs QA

    assert res.status_code == 409 and res.json()["detail"]["code"] in ("already_on_team", "person_unavailable")
    db.expire_all()
    assert world["meena"].team_id is None  # the rest of the list was not added either


def test_the_list_must_have_between_one_and_two_hundred_people(world):
    d, npi = world["d"], world["npi"]

    assert d.call(world["asha"], "POST", f"/teams/{npi['id']}/members/bulk", json={"person_ids": []}).status_code == 422
    assert d.call(world["asha"], "POST", f"/teams/{npi['id']}/members/bulk", json={"person_ids": ["not-an-id"]}).status_code == 422
