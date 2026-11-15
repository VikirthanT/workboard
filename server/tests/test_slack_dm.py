"""The DM card an assignee gets and what they can do on it: queued with the task, sent after, redrawn when the status changes,
a status dropdown whose moves go on the timeline under their name (marked as from Slack), a Comment button, a lock once the
task is Done, and the reasons for moves shown in the card's thread. Slack is a fake throughout. People and work are made up."""
import uuid

import pytest
from sqlalchemy import select

from core.config import settings
from core.exceptions import AppError
from models import Person, SlackDm, SlackDmMessage, Task, TaskActivity
from security.authorization import assignee_transitions_for
from slack import blocks, client, listener
from slack.client import SlackError
from slack.services import announce, dm, interactions
from tasks.services import commands
from tests.conftest import make_team


@pytest.fixture
def slack(monkeypatch):
    """Slack on, with a fake that records the DMs it was asked to send, the cards it was asked to redraw and the thread posts."""
    state = {"opened": [], "posted": [], "updated": [], "fail": None}

    def open_dm(token, slack_user_id):
        if state["fail"]:
            raise state["fail"]
        state["opened"].append(slack_user_id)
        return f"D-{slack_user_id}"

    def post_message(token, channel, text, blocks_, thread_ts=None, color=None):
        state["posted"].append({"channel": channel, "text": text, "blocks": blocks_, "thread_ts": thread_ts, "color": color})
        return f"1700000000.{len(state['posted']):06d}"

    def update_message(token, channel, ts, text, blocks_, color=None):
        state["updated"].append({"channel": channel, "ts": ts, "text": text, "blocks": blocks_, "color": color})

    monkeypatch.setattr(client, "open_dm", open_dm)
    monkeypatch.setattr(client, "post_message", post_message)
    monkeypatch.setattr(client, "update_message", update_message)
    monkeypatch.setattr(announce.client, "post_with_pdf", lambda *a: None)  # the channel post is tested in test_slack_announce.py
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    return state


@pytest.fixture
def world(directory, admin, db):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    ravi.slack_user_id = "U0RAVI1234"  # a real-looking id, so Ravi gets DMs; Meena's made-up one does not
    db.commit()
    team = make_team(directory, admin, "NPI", asha)
    for person in (ravi, meena):
        directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})
    db.expire_all()
    return {"asha": asha, "ravi": ravi, "meena": meena, "team_id": uuid.UUID(team["id"]), "directory": directory}


def create(world, title, who, **extra):
    return world["directory"].call(world["asha"], "POST", "/tasks", json={"title": title, "assignee_id": str(who.id), **extra})


def dms(db):
    db.expire_all()
    return list(db.scalars(select(SlackDm).order_by(SlackDm.created_at)))


def control_ids(card_blocks):
    return [e["action_id"] for b in card_blocks if b["type"] == "actions" for e in b["elements"]]


def dropdown(card_blocks):
    return next((e for b in card_blocks if b["type"] == "actions" for e in b["elements"] if e["type"] == "static_select"), None)


def selected(card_blocks):
    """The status the dropdown shows as chosen, as its label."""
    return dropdown(card_blocks)["initial_option"]["text"]["text"]


def make_task(db, world, status="todo", **extra):
    task = Task(team_id=world["team_id"], title="Design weld jig", status=status, assignee_id=world["ravi"].id, creator_id=world["asha"].id, **extra)
    db.add(task)
    db.commit()
    return task


def make_sent_card(db, world, status="in_progress"):
    task = make_task(db, world, status)
    db.add(SlackDm(task_id=task.id, person_id=world["ravi"].id, status="sent", dm_channel="D1", message_ts="5.5"))
    db.commit()
    return task


# ---- the permission rule ----

@pytest.mark.parametrize("status", ["todo", "in_progress", "blocked", "review"])
def test_an_assignee_may_move_their_task_to_every_other_open_status_backwards_included(db, world, status):
    task = Task(team_id=world["team_id"], title="t", status=status, assignee_id=world["ravi"].id, creator_id=world["asha"].id)

    moves = assignee_transitions_for(world["ravi"], task)

    assert {m.to for m in moves} == {"todo", "in_progress", "blocked", "review"} - {status}
    assert "done" not in {m.to for m in moves}  # the manager decides that
    # A reason for Blocked, as on the board, and for going back to To Do; nothing else needs one.
    assert all(m.needs_reason == (m.to in ("blocked", "todo")) for m in moves)


def test_a_done_task_is_locked_nobody_but_the_manager_moves_it_and_others_have_no_moves(db, world):
    done = Task(team_id=world["team_id"], title="t", status="done", assignee_id=world["ravi"].id, creator_id=world["asha"].id)
    open_ = Task(team_id=world["team_id"], title="t", status="todo", assignee_id=world["ravi"].id, creator_id=world["asha"].id)

    assert assignee_transitions_for(world["ravi"], done) == []
    assert assignee_transitions_for(world["meena"], open_) == []  # someone else's task
    assert assignee_transitions_for(world["asha"], open_) == []  # the manager moves cards on the board, not through this rule


def test_an_inactive_assignee_may_do_nothing(db, world):
    world["ravi"].active = False
    task = Task(team_id=world["team_id"], title="t", status="todo", assignee_id=world["ravi"].id)

    assert assignee_transitions_for(world["ravi"], task) == []


# ---- the commands ----

def test_a_move_is_on_the_timeline_under_the_assignees_name_and_marked_as_slack(db, world):
    task_id = uuid.uuid4()
    commands.create_task(db, world["asha"], task_id, "Design weld jig", "", "medium", None, world["ravi"].id)

    commands.move_task_as_assignee(db, world["ravi"], task_id, "in_progress", None)
    commands.move_task_as_assignee(db, world["ravi"], task_id, "blocked", "Waiting on parts")
    commands.move_task_as_assignee(db, world["ravi"], task_id, "todo", "Parts delayed, not started")  # back is allowed

    entries = list(db.scalars(select(TaskActivity).where(TaskActivity.task_id == task_id, TaskActivity.kind == "status").order_by(TaskActivity.created_at)))
    assert [(e.actor_id, e.source, e.old_value, e.new_value, e.note) for e in entries] == [
        (world["ravi"].id, "slack", "todo", "in_progress", None),
        (world["ravi"].id, "slack", "in_progress", "blocked", "Waiting on parts"),
        (world["ravi"].id, "slack", "blocked", "todo", "Parts delayed, not started"),
    ]
    assert db.get(Task, task_id).status == "todo"


@pytest.mark.parametrize("actor,to,status,code", [
    ("ravi", "done", "in_progress", "invalid_transition"),
    ("ravi", "in_progress", "in_progress", "invalid_transition"),  # already there
    ("ravi", "in_progress", "done", "invalid_transition"),  # locked once Done
    ("ravi", "blocked", "in_progress", "reason_required"),
    ("ravi", "todo", "in_progress", "reason_required"),  # going back needs a reason too
    ("meena", "in_progress", "todo", "forbidden"),
    ("asha", "in_progress", "todo", "forbidden"),
], ids=["not done", "same status", "done is locked", "blocked needs a reason", "back needs a reason", "not someone elses", "not even the manager"])
def test_the_assignees_moves_are_limited(db, world, actor, to, status, code):
    task = make_task(db, world, status)

    with pytest.raises(AppError) as err:
        commands.move_task_as_assignee(db, world[actor], task.id, to, None)

    assert err.value.code == code
    assert db.get(Task, task.id).status == status


# ---- the card ----

def card_for(world, status, due=None, reviewer_note=None):
    task = Task(id=uuid.uuid4(), number=12, team_id=world["team_id"], title="Design <weld> jig", description="Ready & shared.", status=status,
                priority="high", assignee_id=world["ravi"].id, creator_id=world["asha"].id, due_at=due)
    return blocks.card(task, world["ravi"], reviewer_note)


@pytest.mark.parametrize("status,label", [("todo", "To Do"), ("in_progress", "In Progress"), ("blocked", "Blocked"), ("review", "Review")])
def test_an_open_card_has_a_status_dropdown_showing_the_current_status_and_a_comment_button(db, world, status, label):
    text, card = card_for(world, status)

    menu = dropdown(card)
    assert [o["text"]["text"] for o in menu["options"]] == ["To Do", "In Progress", "Blocked", "Review"]  # never Done
    assert selected(card) == label and menu["initial_option"] in menu["options"]
    assert control_ids(card) == [blocks.STATUS_ACTION, blocks.COMMENT_ACTION]
    assert text.startswith("Task #12 ") and f"({label})" in text and "Design <weld> jig" not in str(card)  # the title is escaped


def test_a_done_card_is_locked_and_shows_the_reviewers_last_remarks(db, world):
    _, card = card_for(world, "done", reviewer_note=("Asha", "Shipped & verified <ok>"))

    assert control_ids(card) == [] and dropdown(card) is None  # no dropdown, no Comment
    assert "locked" in str(card) and "removed a few days after" in str(card)
    assert "*Asha* · reviewer\nShipped &amp; verified &lt;ok&gt;" in card[-1]["text"]["text"]
    assert "reviewer" not in str(card_for(world, "done", reviewer_note=None)[1])  # no remarks given: nothing is invented


def test_the_card_says_review_is_waiting_but_can_still_be_moved_back(db, world):
    _, card = card_for(world, "review")

    assert "Waiting for your manager" in str(card) and dropdown(card) is not None


def test_the_card_carries_the_task_number_and_not_a_who_assigned_it_line(db, world):
    text, card = card_for(world, "todo")

    assert "*Task #12*" in str(card) and "New task from" not in str(card)


def test_the_card_has_the_priority_colour_bar(db, world):
    task = Task(id=uuid.uuid4(), number=3, team_id=world["team_id"], title="t", description="", status="todo", assignee_id=world["ravi"].id)
    colours = {}
    for priority in ("high", "medium", "low"):
        task.priority = priority
        colours[priority] = blocks.card_color(task)

    assert colours == {"high": "#cf3f3f", "medium": "#a75c09", "low": "#3cbfad"}


def test_the_card_follows_the_block_kit_rules_a_fake_slack_cannot_check(db, world):
    """Slack refused the first real card because two buttons shared an action_id. These are the rules it enforces that
    matter here, checked on every status: unique action ids and block ids, the sizes it limits, no empty actions, and a
    dropdown whose selected option is one of its options."""
    for status in ("todo", "in_progress", "blocked", "review", "done"):
        _, card = card_for(world, status, reviewer_note=("Asha", "ok"))
        ids = control_ids(card)
        block_ids = [b["block_id"] for b in card if "block_id" in b]
        assert len(ids) == len(set(ids)) and len(block_ids) == len(set(block_ids)) and all(len(i) <= 255 for i in block_ids), status
        assert len(card) <= 50 and all(b["type"] != "actions" or b["elements"] for b in card)
        assert all(len(f["text"]) <= 2000 for b in card if "fields" in b for f in b["fields"])
        for element in (e for b in card if b["type"] == "actions" for e in b["elements"]):
            if element["type"] == "static_select":
                assert 1 <= len(element["options"]) <= 100 and element["initial_option"] in element["options"]
                assert all(len(o["value"]) <= 150 and len(o["text"]["text"]) <= 75 for o in element["options"])
            else:
                assert len(element["value"]) <= 2000 and len(element["text"]["text"]) <= 75


def test_the_bar_colour_is_sent_as_an_attachment_and_plain_blocks_without_one():
    with_bar = client._content("t", [{"type": "divider"}], "#3cbfad")
    plain = client._content("t", [{"type": "divider"}], None)

    # With a bar the text is the attachment's fallback (notifications only): a top-level text would be shown above the card.
    assert with_bar == {"attachments": [{"color": "#3cbfad", "blocks": [{"type": "divider"}], "fallback": "t"}]}
    assert "text" not in with_bar
    assert plain == {"text": "t", "blocks": [{"type": "divider"}]}


# ---- queueing and sending ----

def test_a_new_task_sends_its_assignee_a_dm_card_and_remembers_where(db, world, slack):
    res = create(world, "Design weld jig", world["ravi"], priority="high")

    assert res.status_code == 201
    assert slack["opened"] == ["U0RAVI1234"]
    [post] = slack["posted"]
    assert post["channel"] == "D-U0RAVI1234" and post["color"] == "#cf3f3f" and "Design weld jig" in post["text"]
    assert control_ids(post["blocks"]) == [blocks.STATUS_ACTION, blocks.COMMENT_ACTION]
    [row] = dms(db)
    assert (row.status, row.dm_channel, row.message_ts, row.person_id) == ("sent", "D-U0RAVI1234", "1700000000.000001", world["ravi"].id)


def test_people_with_a_made_up_slack_id_and_unset_up_slack_get_no_card(db, world, slack, monkeypatch):
    create(world, "For Meena", world["meena"])  # a made-up id: skipped
    assert dms(db) == [] and slack["opened"] == []

    monkeypatch.setattr(settings, "slack_bot_token", "")
    create(world, "For Ravi, Slack off", world["ravi"])
    assert dms(db) == []


def test_a_slack_failure_leaves_the_card_pending_and_never_affects_creating_the_task(db, world, slack):
    slack["fail"] = SlackError("Slack refused it: user_not_found.")

    res = create(world, "Design weld jig", world["ravi"])

    assert res.status_code == 201
    [row] = dms(db)
    assert (row.status, row.attempts, row.last_error) == ("pending", 1, "Slack refused it: user_not_found.")

    slack["fail"] = None
    dm.send_pending(world["team_id"])  # the next flush sends it
    assert [r.status for r in dms(db)] == ["sent"] and len(slack["posted"]) == 1


def test_a_card_is_redrawn_when_the_manager_moves_the_task_on_the_board(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    slack["updated"].clear()

    res = world["directory"].call(world["asha"], "POST", f"/tasks/{task_id}/status", json={"to": "in_progress"})

    assert res.status_code == 200
    [update] = slack["updated"]
    assert (update["channel"], update["ts"]) == ("D-U0RAVI1234", "1700000000.000001")
    assert selected(update["blocks"]) == "In Progress" and "In Progress" in str(update["blocks"])


def test_marking_it_done_on_the_board_locks_the_card_and_shows_the_remarks_on_it(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    for to, note in (("in_progress", None), ("review", None), ("done", "Verified on the rig, well done.")):
        world["directory"].call(world["asha"], "POST", f"/tasks/{task_id}/status", json={"to": to, "note": note})

    locked = slack["updated"][-1]

    assert dropdown(locked["blocks"]) is None and control_ids(locked["blocks"]) == []
    assert locked["blocks"][-1]["text"]["text"] == "*Asha* · reviewer\nVerified on the rig, well done."


# ---- the reasons for moves, in the thread ----

def move_on_board(world, task_id, to, note=None, who=None):
    return world["directory"].call(who or world["asha"], "POST", f"/tasks/{task_id}/status", json={"to": to, "note": note})


def test_a_move_with_a_reason_is_posted_in_the_thread_so_the_assignee_can_see_why(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    move_on_board(world, task_id, "in_progress")
    move_on_board(world, task_id, "review")
    slack["posted"].clear()

    move_on_board(world, task_id, "done", "Verified on the rig.\nShip it & celebrate")

    [post] = slack["posted"]
    assert post["thread_ts"] == "1700000000.000001" and post["color"] == blocks.MANAGER_BAR
    body = post["blocks"][0]["text"]["text"]
    assert body.startswith("*Asha* · manager\nMoved it to *Done*\n> Verified on the rig.\n> Ship it &amp; celebrate")
    assert post["text"] == "Asha moved it to Done: Verified on the rig.\nShip it & celebrate"


def test_a_move_without_a_reason_is_still_posted_in_the_thread(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    slack["posted"].clear()

    move_on_board(world, task_id, "in_progress")

    [post] = slack["posted"]
    assert "Moved it to *In Progress*" in post["blocks"][0]["text"]["text"] and ">" not in post["blocks"][0]["text"]["text"]


def test_send_back_and_reopen_reasons_are_posted_too(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    for to, note in (("in_progress", None), ("review", None)):
        move_on_board(world, task_id, to, note)
    slack["posted"].clear()

    move_on_board(world, task_id, "in_progress", "Drawing is missing the tolerance.")  # send back

    assert "Moved it to *In Progress*\n> Drawing is missing the tolerance." in slack["posted"][0]["blocks"][0]["text"]["text"]


def test_an_assignees_own_reason_is_kept_in_the_thread_with_their_bar(db, world, slack):
    task = make_sent_card(db, world, "in_progress")

    assert interactions.move("U0RAVI1234", str(task.id), "blocked", "Waiting on the supplier") is None

    [post] = slack["posted"]
    assert post["thread_ts"] == "5.5" and post["color"] == blocks.ASSIGNEE_BAR
    assert "*Ravi* · you\nMoved it to *Blocked*\n> Waiting on the supplier" in post["blocks"][0]["text"]["text"]


# ---- the button handlers ----

def test_choosing_a_status_moves_the_task_and_redraws_the_card(db, world, slack):
    task = make_sent_card(db, world, "todo")

    assert interactions.move("U0RAVI1234", str(task.id), "in_progress", None) is None

    db.expire_all()
    assert db.get(Task, task.id).status == "in_progress"
    assert slack["updated"][-1]["ts"] == "5.5" and selected(slack["updated"][-1]["blocks"]) == "In Progress"
    [post] = slack["posted"]  # no reason given, but the move itself is posted in the thread
    assert "Moved it to *In Progress*" in post["blocks"][0]["text"]["text"]


def test_moving_back_is_allowed_and_asks_for_a_reason(db, world, slack):
    task = make_sent_card(db, world, "in_progress")

    assert "reason" in interactions.move("U0RAVI1234", str(task.id), "todo", None)
    assert interactions.move("U0RAVI1234", str(task.id), "todo", "Not started after all") is None

    db.expire_all()
    assert db.get(Task, task.id).status == "todo"


@pytest.mark.parametrize("who,to,reason,fragment", [
    ("UNOBODY999", "in_progress", None, "could not find you"),
    ("U0RAVI1234", "done", None, "cannot move"),
    ("U0RAVI1234", "blocked", None, "reason"),
], ids=["unknown person", "done", "blocked without a reason"])
def test_a_refused_choice_says_why_changes_nothing_and_puts_the_dropdown_back(db, world, slack, who, to, reason, fragment):
    task = make_sent_card(db, world, "todo")

    message = interactions.move(who, str(task.id), to, reason)

    assert fragment in message
    db.expire_all()
    assert db.get(Task, task.id).status == "todo"
    if who != "UNOBODY999":
        assert selected(slack["updated"][-1]["blocks"]) == "To Do"  # the card was redrawn from the real status


def test_a_locked_card_cannot_be_moved_even_from_an_old_message(db, world, slack):
    task = make_sent_card(db, world, "done")

    assert "cannot move" in interactions.move("U0RAVI1234", str(task.id), "in_progress", "reopen please")


def test_someone_elses_task_and_a_bad_id_are_refused(db, world, slack):
    task = make_task(db, world)
    meena = db.get(Person, world["meena"].id)
    meena.slack_user_id = "U0MEENA999"
    db.commit()

    assert "assigned to can move" in interactions.move("U0MEENA999", str(task.id), "in_progress", None)
    assert interactions.move("U0RAVI1234", "not-a-uuid", "in_progress", None) == "That task could not be found."


def test_a_reason_form_opens_for_blocked_and_back_to_todo_and_asks_to_be_told_when_closed(db, world):
    task = make_task(db, world, "in_progress")

    for to, title in (("blocked", "Why is it blocked?"), ("todo", "Why move it back?")):
        view, problem = interactions.reason_view("U0RAVI1234", str(task.id), to)
        assert problem is None and view["callback_id"] == "wb_reason" and view["private_metadata"] == f"{task.id}|{to}"
        assert view["title"]["text"] == title and view["notify_on_close"] is True  # so a cancel can reset the dropdown
        assert len(view["title"]["text"]) <= 24 and len(view["submit"]["text"]) <= 24  # Slack's limits on a modal's buttons and title
        assert view["blocks"][0]["label"]["text"] == "Reason"  # not the task's title, which only repeated the card

    assert interactions.reason_view("U0RAVI1234", str(task.id), "done")[0] is None
    assert interactions.reason_view("UNOBODY999", str(task.id), "blocked")[0] is None


def test_cancelling_the_reason_form_redraws_the_card_from_its_real_status(db, world, slack):
    task = make_sent_card(db, world, "in_progress")

    interactions.reset_card(str(task.id))
    interactions.reset_card("not-a-uuid")  # nothing to do, and no error

    assert selected(slack["updated"][-1]["blocks"]) == "In Progress"


# ---- comments from the assignee ----

def test_an_assignees_comment_is_on_the_timeline_under_their_name_marked_as_slack(db, world):
    task_id = uuid.uuid4()
    commands.create_task(db, world["asha"], task_id, "Design weld jig", "", "medium", None, world["ravi"].id)

    commands.add_comment_as_assignee(db, world["ravi"], task_id, uuid.uuid4(), "  Parts arrived.  ")

    [entry] = db.scalars(select(TaskActivity).where(TaskActivity.task_id == task_id, TaskActivity.kind == "comment")).all()
    assert (entry.actor_id, entry.source, entry.note) == (world["ravi"].id, "slack", "Parts arrived.")


@pytest.mark.parametrize("actor,status,text,code", [
    ("meena", "todo", "hi", "forbidden"),
    ("asha", "todo", "hi", "forbidden"),  # the manager comments on the board
    ("ravi", "done", "hi", "task_done"),
    ("ravi", "todo", "   ", "comment_required"),
    ("ravi", "todo", "x" * 1001, "comment_too_long"),
])
def test_who_may_comment_from_slack_and_what(db, world, actor, status, text, code):
    task = make_task(db, world, status)

    with pytest.raises(AppError) as err:
        commands.add_comment_as_assignee(db, world[actor], task.id, uuid.uuid4(), text)

    assert err.value.code == code


def test_pressing_comment_saves_it_and_posts_it_in_the_cards_thread_with_the_assignees_bar(db, world, slack):
    task = make_sent_card(db, world)

    assert interactions.comment("U0RAVI1234", str(task.id), "  Parts arrived. ") is None

    [post] = slack["posted"]
    assert post["thread_ts"] == "5.5" and post["channel"] == "D1" and post["color"] == blocks.ASSIGNEE_BAR
    assert post["blocks"][0]["text"]["text"] == "*Ravi* · you\nParts arrived."
    db.expire_all()
    assert db.scalar(select(TaskActivity.note).where(TaskActivity.task_id == task.id, TaskActivity.kind == "comment")) == "Parts arrived."
    assert [m.ts for m in db.scalars(select(SlackDmMessage))] == ["1700000000.000001"]  # remembered, so the thread can be removed later


@pytest.mark.parametrize("who,text,fragment", [
    ("UNOBODY999", "hi", "could not find you"),
    ("U0RAVI1234", "   ", "Write a comment"),
])
def test_a_refused_comment_says_why_and_posts_nothing(db, world, slack, who, text, fragment):
    task = make_sent_card(db, world)

    assert fragment in interactions.comment(who, str(task.id), text)
    assert slack["posted"] == []


def test_the_comment_form_opens_only_while_the_person_may_comment(db, world):
    task = make_sent_card(db, world)

    view, problem = interactions.comment_view("U0RAVI1234", str(task.id))
    assert problem is None and view["callback_id"] == "wb_comment_submit" and view["private_metadata"] == str(task.id)

    task.status = "done"
    db.commit()
    assert interactions.comment_view("U0RAVI1234", str(task.id))[0] is None


# ---- the manager's comment, shown in the thread ----

def board_comment(world, task_id, who, text):
    return world["directory"].call(who, "POST", f"/tasks/{task_id}/comments", json={"body": text})


def test_a_comment_on_the_board_appears_in_the_assignees_thread_with_the_managers_bar(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    slack["posted"].clear()

    res = board_comment(world, task_id, world["asha"], "Please share the drawing.")

    assert res.status_code == 201
    [post] = slack["posted"]
    assert post["thread_ts"] == "1700000000.000001" and post["color"] == blocks.MANAGER_BAR  # under the card
    assert post["blocks"][0]["text"]["text"] == "*Asha* · manager\nPlease share the drawing."


def test_an_admins_comment_is_labelled_admin(db, world, slack, admin):
    task_id = create(world, "Design weld jig", world["ravi"]).json()["id"]
    slack["posted"].clear()

    assert board_comment(world, task_id, admin, "Looks fine to me.").status_code == 201

    assert slack["posted"][0]["blocks"][0]["text"]["text"].startswith("*Admin* · admin")


def test_a_slack_comment_is_not_echoed_back_and_a_slack_failure_never_breaks_the_board(db, world, slack, monkeypatch):
    task = make_sent_card(db, world)
    commands.add_comment_as_assignee(db, world["ravi"], task.id, entry_id := uuid.uuid4(), "From Slack")

    dm.post_manager_comment(task.id, entry_id)  # a Slack-sourced entry: nothing to post
    assert slack["posted"] == []

    task_id = create(world, "Another", world["ravi"]).json()["id"]

    def refuse(*args, **kwargs):
        raise SlackError("Slack refused it: channel_not_found.")

    monkeypatch.setattr(client, "post_message", refuse)
    assert board_comment(world, task_id, world["asha"], "Hello").status_code == 201  # the comment is saved regardless


def test_no_card_no_thread_message(db, world, slack):
    task = make_task(db, world)  # no DM card was ever sent for it

    dm.post_comment(task.id, "Asha", "manager", "Anyone there?")
    dm.post_move(task.id, world["asha"].id, "done", "Finished")

    assert slack["posted"] == []


# ---- the listener ----

def test_the_listener_builds_offline_and_stays_quiet_without_tokens(capsys):
    assert listener.build_app("xoxb-test", verify=False) is not None

    listener.main()  # no tokens in the tests

    assert "Slack listener not started" in capsys.readouterr().out
