"""The Slack side seen from the outside: each real route (create a task, upload a sheet, add standup suggestions, move a
task) with Slack faked at its edge, checking what reaches the team's channel and what reaches the assignee's DM.
People and work are made up."""
import uuid
from datetime import date, timedelta

import pytest

from core.config import settings
from models import TaskSuggestion
from slack import client
from slack.client import SlackError
from slack.services import announce
from standups.llm import extract
from tests.conftest import make_team
from tests.test_task_import_parse import sheet

TODAY = date.today()


@pytest.fixture
def slack(monkeypatch):
    """Slack on. `channel` records the channel posts (with their PDF), `dms` the people DMs were opened for, `posted` the
    card and thread messages. `fail_channel` makes the channel post fail."""
    state = {"channel": [], "dms": [], "posted": [], "fail_channel": None}

    def post_with_pdf(token, channel, text, filename, pdf):
        if state["fail_channel"]:
            raise state["fail_channel"]
        state["channel"].append({"channel": channel, "text": text, "filename": filename, "pdf": pdf})

    def open_dm(token, slack_user_id):
        state["dms"].append(slack_user_id)
        return f"D-{slack_user_id}"

    def post_message(token, channel, text, blocks_, thread_ts=None, color=None):
        state["posted"].append({"channel": channel, "text": text, "blocks": blocks_, "thread_ts": thread_ts})
        return f"1700000000.{len(state['posted']):06d}"

    monkeypatch.setattr(announce.client, "post_with_pdf", post_with_pdf)
    monkeypatch.setattr(client, "open_dm", open_dm)
    monkeypatch.setattr(client, "post_message", post_message)
    monkeypatch.setattr(client, "update_message", lambda *a, **k: None)
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    return state


@pytest.fixture
def world(directory, admin, db):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    ravi.slack_user_id = "U0RAVI1234"  # a real-looking id: tagged in the channel and sent DMs; Meena's made-up one is neither
    db.commit()
    team = make_team(directory, admin, "NPI", asha)
    for person in (ravi, meena):
        directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})
    db.expire_all()
    return {"asha": asha, "ravi": ravi, "meena": meena, "team_id": team["id"], "directory": directory}


def cards(slack):
    """The DM cards (top-level messages), as opposed to the replies in a card's thread."""
    return [p for p in slack["posted"] if p["thread_ts"] is None]


def thread(slack):
    return [p for p in slack["posted"] if p["thread_ts"] is not None]


def upload(world, *rows):
    return world["directory"].call(
        world["asha"], "POST", "/tasks/import", files={"file": ("tasks.xlsx", sheet(*rows), "application/octet-stream")}
    )


def test_a_task_created_on_the_board_dms_the_assignee_and_posts_nothing_in_the_channel(world, slack):
    res = world["directory"].call(
        world["asha"], "POST", "/tasks", json={"title": "Design weld jig", "assignee_id": str(world["ravi"].id), "project": "P1", "stage": "Design"}
    )

    assert res.status_code == 201
    assert slack["channel"] == []
    assert slack["dms"] == ["U0RAVI1234"] and len(cards(slack)) == 1
    [context] = [b for b in cards(slack)[0]["blocks"] if b["type"] == "context"]
    assert context["elements"][0]["text"] == "`P1`  `Design`"  # the project and stage tags under the title
    fields = [f["text"] for b in cards(slack)[0]["blocks"] for f in b.get("fields", [])]
    assert any(f.startswith("*Created*\n`") for f in fields) and any(f.startswith("*Due*\n`") for f in fields)


def test_a_bulk_upload_posts_one_channel_message_with_a_pdf_and_dms_each_assignee(world, slack):
    res = upload(
        world,
        {"Title": "Wire harness", "Assignee": "ravi"},
        {"Title": "Order brackets", "Assignee": "ravi"},
        {"Title": "Check fixtures", "Assignee": "meena"},
    )

    assert (res.status_code, res.json()) == (201, {"created": 3})
    [post] = slack["channel"]
    assert post["channel"] == "C0TEST" and post["pdf"].startswith(b"%PDF")
    assert post["filename"] == f"Task-{TODAY.strftime('%d-%b-%Y')}.pdf"
    assert post["text"].startswith("*Added tasks*")
    assert "<@U0RAVI1234> - 2 tasks" in post["text"] and "*Meena* - 1 task" in post["text"]
    assert "Wire harness" not in post["text"]  # the titles are in the PDF only
    assert "see your Slack DM from the Workboard bot" in post["text"]
    assert set(slack["dms"]) == {"U0RAVI1234"}
    assert len(cards(slack)) == 2  # Ravi's two tasks; Meena has no real Slack id


def test_the_managers_own_tasks_are_left_out_of_the_channel_post_and_the_pdf(world, slack, monkeypatch):
    in_pdf = []
    real_build = announce.build_pdf
    monkeypatch.setattr(announce, "build_pdf", lambda team, by, tasks, today: in_pdf.extend(t.title for t in tasks) or real_build(team, by, tasks, today))

    upload(world, {"Title": "Mine", "Assignee": "asha"}, {"Title": "Ravis", "Assignee": "ravi"})

    [post] = slack["channel"]
    assert "<@U0RAVI1234> - 1 task" in post["text"] and "Asha" not in post["text"]
    assert in_pdf == ["Ravis"]

    slack["channel"].clear()
    upload(world, {"Title": "Only mine", "Assignee": "asha"})
    assert slack["channel"] == []  # a batch of only the manager's tasks posts nothing


def test_a_rejected_upload_sends_nothing_anywhere(world, slack):
    res = upload(world, {"Title": "Fine", "Assignee": "ravi"}, {"Title": "", "Assignee": "ravi"})

    assert res.status_code == 422
    assert slack["channel"] == [] and slack["posted"] == [] and slack["dms"] == []


def test_adding_standup_suggestions_posts_the_standup_heading_and_dms_the_assignee(db, world, slack):
    ids = []
    for title in ("Design weld jig", "Order bracket samples"):
        s = TaskSuggestion(
            team_id=uuid.UUID(world["team_id"]), person_id=world["ravi"].id, source_submission_id=1, standup_date=TODAY,
            title=title, title_key=extract.norm(title), description="", kind="new", priority="medium",
            evidence_quote="a line", model="m", prompt_hash="h", due_at=TODAY + timedelta(days=3),
        )
        db.add(s)
        db.commit()
        ids.append(str(s.id))

    res = world["directory"].call(world["asha"], "POST", f"/teams/{world['team_id']}/suggestions/add", json={"suggestion_ids": ids})

    assert res.status_code == 200, res.text
    [post] = slack["channel"]
    assert post["text"].startswith("*Tasks from Standup*") and "<@U0RAVI1234> - 2 tasks" in post["text"]
    assert len(cards(slack)) == 2


def test_a_channel_failure_never_breaks_the_upload_and_the_dms_still_go(world, slack):
    slack["fail_channel"] = SlackError("Slack refused it: not_in_channel.")

    res = upload(world, {"Title": "Wire harness", "Assignee": "ravi"})

    assert (res.status_code, res.json()) == (201, {"created": 1})
    assert slack["channel"] == [] and len(cards(slack)) == 1


def test_every_move_on_the_board_is_posted_in_the_dm_thread_with_its_reason(world, slack):
    task_id = world["directory"].call(world["asha"], "POST", "/tasks", json={"title": "Design weld jig", "assignee_id": str(world["ravi"].id)}).json()["id"]
    slack["posted"].clear()

    for to, note in (("in_progress", None), ("blocked", "Waiting for the supplier"), ("in_progress", None), ("review", None), ("done", "Verified on the rig")):
        res = world["directory"].call(world["asha"], "POST", f"/tasks/{task_id}/status", json={"to": to, "note": note})
        assert res.status_code == 200, (to, res.text)

    bodies = [p["blocks"][0]["text"]["text"] for p in thread(slack)]
    assert len(bodies) == 5
    for body, label in zip(bodies, ("In Progress", "Blocked", "In Progress", "Review", "Done")):
        assert f"Moved it to *{label}*" in body
    assert "> Waiting for the supplier" in bodies[1] and "> Verified on the rig" in bodies[4]
    assert ">" not in bodies[0]  # no reason, no quote
    assert slack["channel"] == []  # moves never go to the channel
