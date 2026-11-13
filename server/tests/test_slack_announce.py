"""The Slack announcement of new tasks: queued with the task, sent afterwards as one message and one PDF, and never able to
break creating the task. Slack itself is a fake; no test ever reaches the real one. People and work are made up."""
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.config import settings
from models import SlackOutbox, Task, Team
from slack import client, messages
from slack.client import SlackError
from slack.pdf import AnnouncedTask, build_pdf, by_person, latin1
from slack.services import announce
from tasks.services import commands
from tests.conftest import make_team

TODAY = date.today()


@pytest.fixture
def slack(monkeypatch):
    """Turns Slack on with a fake token and records what would have been posted. `fail` makes the next posts fail."""
    state = {"posts": [], "fail": None}

    def post(token, channel, text, filename, pdf):
        if state["fail"]:
            raise state["fail"]
        state["posts"].append({"token": token, "channel": channel, "text": text, "filename": filename, "pdf": pdf})

    monkeypatch.setattr(announce.client, "post_with_pdf", post)
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    return state


@pytest.fixture
def world(directory, admin, db):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    ravi.slack_user_id = "U0RAVI1234"  # a real-looking Slack id, so Ravi is tagged; Meena keeps a made-up one
    db.commit()
    team = make_team(directory, admin, "NPI", asha)
    for person in (ravi, meena):
        directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})
    db.expire_all()  # the team was made through the API in another session: reload who is on it before calling services directly
    return {"asha": asha, "ravi": ravi, "meena": meena, "team_id": uuid.UUID(team["id"]), "directory": directory, "db": db}


def create(world, title, who, db=None, **extra):
    """Adds a task the way a standup-suggestion batch does (the only path that is announced in the channel), then
    flushes like the router does. Returns something shaped like the API's response."""
    db = db or world["db"]
    task_id = uuid.uuid4()
    commands.add_task_uncommitted(
        db, world["asha"], db.get(Team, world["team_id"]), task_id, title, extra.get("description", ""),
        extra.get("priority", "medium"), date.fromisoformat(extra["due_at"]) if extra.get("due_at") else None, who.id,
    )
    db.commit()
    announce.flush_team(world["team_id"])
    return SimpleNamespace(status_code=201, json=lambda: {"id": str(task_id)})


def outbox(db):
    db.expire_all()
    return list(db.scalars(select(SlackOutbox).order_by(SlackOutbox.created_at)))


def test_a_new_task_is_announced_in_the_teams_channel_with_a_pdf_and_a_tag(db, world, slack):
    res = create(world, "Design weld jig", world["ravi"], priority="high", due_at=(TODAY + timedelta(days=3)).isoformat(), description="The jig is ready.")

    assert res.status_code == 201
    [post] = slack["posts"]
    assert (post["token"], post["channel"]) == ("xoxb-test", "C0TEST")  # the team's standup channel
    assert "*Added tasks*" in post["text"]
    assert "<@U0RAVI1234> - 1 task" in post["text"] and "Design weld jig" not in post["text"]
    assert post["pdf"].startswith(b"%PDF") and post["filename"] == f"Task-{TODAY.strftime('%d-%b-%Y')}.pdf"
    assert [r.status for r in outbox(db)] == ["sent"] and outbox(db)[0].sent_at is not None


def test_a_task_added_one_at_a_time_is_not_announced_in_the_channel(db, world, slack):
    res = world["directory"].call(world["asha"], "POST", "/tasks", json={"title": "Solo task", "assignee_id": str(world["ravi"].id)})

    assert res.status_code == 201
    assert outbox(db) == [] and slack["posts"] == []  # the assignee's DM is the notification


def test_nothing_is_queued_or_sent_when_slack_is_not_set_up(db, world, monkeypatch):
    sent = []
    monkeypatch.setattr(announce.client, "post_with_pdf", lambda *a: sent.append(a))

    assert create(world, "Design weld jig", world["ravi"]).status_code == 201

    assert outbox(db) == [] and sent == []  # settings.slack_bot_token is empty in tests


def test_several_new_tasks_go_out_as_one_message_numbered_per_person_most_urgent_first(db, world, slack):
    for title, who, priority in (("Low one", world["ravi"], "low"), ("High one", world["ravi"], "high"), ("Meenas task", world["meena"], "medium")):
        commands.add_task_uncommitted(db, world["asha"], db.get(Team, world["team_id"]), uuid.uuid4(), title, "", priority, None, who.id)
    db.commit()

    announce.flush_team(world["team_id"])

    [post] = slack["posts"]
    text = post["text"]
    assert "*Added tasks*" in text
    assert "*Tasks from Standup*" in messages.announcement([task("x")], messages.HEADING_STANDUP)
    assert "*Meena* - 1 task" in text and "<@U0RAVI1234> - 2 tasks" in text  # a made-up Slack id is not turned into a tag
    assert {r.status for r in outbox(db)} == {"sent"}


def test_a_slack_failure_never_affects_creating_the_task_and_is_retried_with_the_next_batch(db, world, slack):
    slack["fail"] = SlackError("Slack refused it: not_in_channel.")

    res = create(world, "First task", world["ravi"])

    assert res.status_code == 201  # the person who created it sees nothing wrong
    [row] = outbox(db)
    assert (row.status, row.attempts, row.last_error) == ("pending", 1, "Slack refused it: not_in_channel.")
    assert slack["posts"] == []

    slack["fail"] = None
    create(world, "Second task", world["ravi"])

    [post] = slack["posts"]
    assert "<@U0RAVI1234> - 2 tasks" in post["text"]
    assert {r.status for r in outbox(db)} == {"sent"}


def test_after_too_many_failures_a_row_is_marked_failed_and_no_longer_tried(db, world, slack):
    slack["fail"] = SlackError("Slack refused it: channel_not_found.")
    create(world, "First task", world["ravi"])

    for _ in range(announce.MAX_ATTEMPTS):
        announce.flush_team(world["team_id"])

    [row] = outbox(db)
    assert (row.status, row.attempts) == ("failed", announce.MAX_ATTEMPTS)
    slack["fail"] = None
    announce.flush_team(world["team_id"])
    assert slack["posts"] == []  # a failed row is not picked up again


def test_a_team_without_a_channel_cannot_be_announced_to_and_its_rows_are_failed(db, world, slack):
    team = db.get(Team, world["team_id"])
    team.standup_channel_id = None
    db.commit()

    create(world, "First task", world["ravi"])

    [row] = outbox(db)
    assert row.status == "failed" and "no standup channel" in row.last_error and slack["posts"] == []


def test_an_unexpected_error_while_announcing_is_swallowed(db, world, slack, monkeypatch):
    def boom(*args):
        raise RuntimeError("the PDF library broke")
    monkeypatch.setattr(announce, "build_pdf", boom)

    assert create(world, "First task", world["ravi"]).status_code == 201

    assert slack["posts"] == [] and [r.status for r in outbox(db)] == ["pending"]  # still queued for the next batch


def test_a_task_deleted_before_it_was_announced_is_not_announced(db, world, slack):
    slack["fail"] = SlackError("Slack refused it: not_in_channel.")
    task_id = create(world, "Mistaken task", world["ravi"]).json()["id"]
    assert len(outbox(db)) == 1
    slack["fail"] = None

    world["directory"].call(world["asha"], "DELETE", f"/tasks/{task_id}")
    announce.flush_team(world["team_id"])

    assert slack["posts"] == [] and outbox(db) == []  # the row went with the task


def test_the_same_tasks_are_not_announced_twice(db, world, slack):
    commands.add_task_uncommitted(db, world["asha"], db.get(Team, world["team_id"]), uuid.uuid4(), "Once", "", "medium", None, world["ravi"].id)
    db.commit()

    announce.flush_team(world["team_id"])
    announce.flush_team(world["team_id"])

    assert len(slack["posts"]) == 1
    assert db.scalar(select(Task.id)) is not None


# ---- the pieces ----

def task(title, who="Ravi", slack_id="U0RAVI1234", priority="medium", due=None, description=""):
    return AnnouncedTask(title=title, description=description, priority=priority, due_at=due, start_at=None, assignee_name=who, assignee_slack_id=slack_id)


def test_the_message_escapes_a_name_pluralises_and_leaves_out_task_details():
    text = messages.announcement([task("Fix <this> & that", who="A&B", slack_id=None), task("Second", who="A&B", slack_id=None)])

    assert "*A&amp;B* - 2 tasks" in text
    assert "Fix" not in text and "Second" not in text and "Slack DM from the Workboard bot" in text


def test_people_are_grouped_and_sorted_most_urgent_first_with_no_date_last():
    rows = by_person([
        task("c", priority="low"), task("b", priority="high", due=date(2026, 11, 20)), task("a", priority="high", due=date(2026, 11, 14)),
        task("n", priority="high"), task("other", who="Meena"),
    ])

    assert list(rows) == ["Ravi", "Meena"]
    assert [t.title for t in rows["Ravi"]] == ["a", "b", "n", "c"]


def test_the_pdf_has_the_mockups_parts_and_survives_characters_its_fonts_do_not_have():
    tasks = [
        AnnouncedTask("Order ₹ samples “now”", "Plenty of text " * 80, "high", TODAY + timedelta(days=2), TODAY, "Ravi", None, "ravi@example.test", "Start the “weld jig” design"),
        AnnouncedTask("Second", "", "low", None, None, "Meena", None),
    ]

    pdf = build_pdf("NPI", "Asha", tasks, TODAY, compress=False)  # uncompressed, so the text can be read from the bytes

    assert pdf.startswith(b"%PDF")
    for part in (b"Tasks added to the Work Board", b"NPI team", b"added by Asha", b"Tasks created", b"People", b"High priority", b"Due within 7 days",
                 b"Ravi", b"ravi@example.test", b"Meena", b"From the standup", b"Task", b"Due no date", b"page 1 of "):
        assert part in pdf, part
    assert latin1("₹5 “x” – é ✓") == 'Rs 5 "x" - é ?'  # typographic marks made plain, anything unknown replaced, never an error


def test_many_tasks_run_onto_more_pages_each_with_its_page_number():
    tasks = [AnnouncedTask(f"Task {n}", "A description that takes a line or two to say what done looks like.", "medium", None, None, "Ravi", None) for n in range(24)]

    pdf = build_pdf("NPI", "Asha", tasks, TODAY, compress=False)

    assert b"page 1 of " in pdf and b"page 2 of " in pdf


def test_a_refused_message_keeps_slacks_own_explanation_of_what_is_wrong_but_never_the_token(monkeypatch):
    class Reply:
        status_code = 200
        def json(self):
            return {"ok": False, "error": "invalid_blocks", "response_metadata": {"messages": ["[ERROR] `action_id` \"x\" already exists [json-pointer:/blocks/2]"]}}

    monkeypatch.setattr(client, "_post", lambda url, **kw: Reply())

    with pytest.raises(SlackError) as err:
        client.post_message("xoxb-secret", "D1", "t", [])

    assert "invalid_blocks" in str(err.value) and "already exists" in str(err.value) and "xoxb-secret" not in str(err.value)


def test_the_slack_upload_is_three_calls_and_an_error_never_contains_the_token(monkeypatch):
    calls = []

    class Reply:
        def __init__(self, status=200, body=None):
            self.status_code, self._body = status, body or {"ok": True}
        def json(self):
            return self._body

    replies = [Reply(body={"ok": True, "upload_url": "https://files.example.test/up", "file_id": "F1"}), Reply(), Reply()]
    monkeypatch.setattr(client, "_post", lambda url, **kw: calls.append((url, kw)) or replies[len(calls) - 1])

    client.post_with_pdf("xoxb-secret", "C0NPI", "the message", "tasks.pdf", b"%PDF-1")

    assert [c[0] for c in calls] == [f"{client.API}/files.getUploadURLExternal", "https://files.example.test/up", f"{client.API}/files.completeUploadExternal"]
    assert calls[0][1]["data"] == {"filename": "tasks.pdf", "length": "6"} and calls[1][1]["content"] == b"%PDF-1"
    assert calls[2][1]["json"] == {"files": [{"id": "F1", "title": "tasks.pdf"}], "channel_id": "C0NPI", "initial_comment": "the message"}

    refused = [Reply(body={"ok": False, "error": "not_in_channel"})]
    monkeypatch.setattr(client, "_post", lambda url, **kw: refused[0])
    with pytest.raises(SlackError) as err:
        client.post_with_pdf("xoxb-secret", "C0NPI", "m", "t.pdf", b"x")
    assert "not_in_channel" in str(err.value) and "xoxb-secret" not in str(err.value)
