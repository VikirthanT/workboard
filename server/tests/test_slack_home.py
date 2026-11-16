"""The Home tab of the bot: what a person sees when they open it, the Stage filter, the controls on each row, and that it is
redrawn after a move. Slack is a fake; people and work are made up."""
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from core.config import settings
from models import Task
from slack import blocks, client
from slack.services import announce, home, interactions
from tests.conftest import make_team

TODAY = date.today()


@pytest.fixture
def slack(monkeypatch):
    """Slack on; records every Home tab published as (slack user id, view)."""
    state = {"homes": []}
    monkeypatch.setattr(client, "publish_home", lambda token, user, view: state["homes"].append((user, view)))
    monkeypatch.setattr(client, "open_dm", lambda token, user: f"D-{user}")
    monkeypatch.setattr(client, "post_message", lambda *a, **k: "1700000000.000001")
    monkeypatch.setattr(client, "update_message", lambda *a, **k: None)
    monkeypatch.setattr(announce.client, "post_with_pdf", lambda *a: None)
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    return state


@pytest.fixture
def world(directory, admin, db):
    asha, ravi, meena = directory.person("Asha"), directory.person("Ravi"), directory.person("Meena")
    ravi.slack_user_id = "U0RAVI1234"
    meena.slack_user_id = "U0MEENA123"
    db.commit()
    team = make_team(directory, admin, "NPI", asha)
    for person in (ravi, meena):
        directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(person.id)})
    db.expire_all()
    return {"asha": asha, "ravi": ravi, "meena": meena, "directory": directory}


def create(world, title, who, **extra):
    res = world["directory"].call(world["asha"], "POST", "/tasks", json={"title": title, "assignee_id": str(who.id), **extra})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def texts(view):
    """Every piece of text in the view, in order, so a test can look for what a person would read."""
    out = []
    for b in view["blocks"]:
        if b["type"] in ("section", "header") and "text" in b:
            out.append(b["text"]["text"])
        for e in b.get("elements", []):
            if "text" in e and isinstance(e["text"], str):
                out.append(e["text"])
    return out


def rows(view):
    return [t for t in texts(view) if t.startswith(tuple(blocks.PRIORITY_DOT.values()))]


def finish(db, task_id, days_ago=0):
    """Mark a task Done the way a move does: the status, and the day it was closed."""
    task = db.get(Task, uuid.UUID(task_id))
    task.status, task.closed_at = "done", datetime.now(timezone.utc) - timedelta(days=days_ago)
    db.commit()


def test_opening_the_home_tab_shows_that_persons_open_tasks_grouped_by_status_then_their_done_ones(db, world, slack):
    create(world, "Ravis todo", world["ravi"])
    blocked = create(world, "Ravis blocked", world["ravi"])
    done = create(world, "Ravis done", world["ravi"])
    create(world, "Meenas task", world["meena"])
    for task_id, status in ((blocked, "blocked"), (done, "done")):
        db.get(Task, uuid.UUID(task_id)).status = status
    db.commit()

    home.publish("U0RAVI1234")

    [(user, view)] = slack["homes"]
    assert user == "U0RAVI1234" and view["type"] == "home"
    found = rows(view)
    assert len(found) == 3 and "Ravis blocked" in found[0] and "Ravis todo" in found[1]  # blocked first
    assert "Ravis done" in found[2]  # the finished one comes last, under its own heading
    assert "Meenas task" not in " ".join(texts(view))
    assert any("*Blocked*" in t for t in texts(view)) and any("*To Do*" in t for t in texts(view)) and any("*Done*" in t for t in texts(view))
    assert "2 open" in " ".join(texts(view)) and "1 done" in " ".join(texts(view))


def test_a_done_row_has_what_it_was_when_it_finished_its_due_and_assigned_dates_and_no_buttons(db, world, slack):
    due = (TODAY + timedelta(days=4)).isoformat()
    task_id = create(world, "Design weld jig", world["ravi"], description="The jig\ndesign is ready.", due_at=due)
    finish(db, task_id, days_ago=1)

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    [row] = rows(view)
    assert "Design weld jig" in row and "Completed " in row and "Due " in row and "Assigned " in row
    assert "The jig design is ready." in row  # the description, its line breaks folded
    assert not [b for b in view["blocks"] if b["type"] == "actions" and b.get("block_id") == f"wb_home_{task_id}"]  # no controls


def test_only_the_latest_done_tasks_are_listed_newest_first_and_the_tab_stays_inside_slacks_limit(db, world, slack):
    for n in range(blocks.HOME_MAX_DONE + 3):
        finish(db, create(world, f"Finished {n}", world["ravi"]), days_ago=n)  # Finished 0 is the newest

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    found = rows(view)
    assert len(found) == blocks.HOME_MAX_DONE and "Finished 0" in found[0] and f"Finished {blocks.HOME_MAX_DONE - 1}" in found[-1]
    assert any(f"Showing the {blocks.HOME_MAX_DONE} most recently completed" in t for t in texts(view)) and len(view["blocks"]) < 100


def test_the_show_dropdown_can_pick_done_and_open_filters_leave_done_out(db, world, slack):
    create(world, "Still open", world["ravi"])
    finish(db, create(world, "Finished one", world["ravi"]))

    home.publish("U0RAVI1234", status="done")
    home.publish("U0RAVI1234", status="todo")

    (_, only_done), (_, only_todo) = slack["homes"]
    assert ["Finished one" in r for r in rows(only_done)] == [True] and ["Still open" in r for r in rows(only_todo)] == [True]
    show = next(e for b in only_done["blocks"] if b.get("block_id") == "wb_home_filter" for e in b["elements"] if e["action_id"] == blocks.HOME_STATUS_FILTER_ACTION)
    assert show["initial_option"]["value"] == "done" and show["initial_option"]["text"]["text"] == "Done (1)"


def test_a_person_with_only_done_tasks_still_sees_them(db, world, slack):
    finish(db, create(world, "Finished one", world["ravi"]))

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    assert len(rows(view)) == 1 and "0 open" in " ".join(texts(view)) and "Nothing open right now." not in texts(view)


def test_each_row_has_the_priority_dot_tags_due_date_and_the_cards_controls(db, world, slack):
    create(world, "Design weld jig", world["ravi"], priority="high", project="P1", stage="Design", due_at=(TODAY + timedelta(days=1)).isoformat())

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    [row] = rows(view)
    assert row.startswith(":red_circle: *Task #") and "Design weld jig" in row and "`P1`  `Design`" in row and "Due " in row
    assert re.search(r"Created \w{3} \d{1,2} \w{3}, \d{1,2}:\d{2} [AP]M$", row)  # the day and time it was made, as the last thing on the row
    [actions] = [b for b in view["blocks"] if b["type"] == "actions" and b["block_id"] != "wb_home_filter"]
    kinds = {e["action_id"] for e in actions["elements"]}
    assert kinds == {blocks.STATUS_ACTION, blocks.COMMENT_ACTION, blocks.HOME_DETAILS_ACTION}  # the DM card's handlers, plus Details
    assert "due in the next 2 days" in " ".join(texts(view))


def test_an_overdue_task_says_how_many_days_in_bold(db, world, slack):
    task_id = create(world, "Late one", world["ravi"], due_at=(TODAY + timedelta(days=3)).isoformat())
    db.get(Task, uuid.UUID(task_id)).due_at = TODAY - timedelta(days=2)
    db.commit()

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    assert "*Overdue by 2 days*" in rows(view)[0] and "*1 overdue*" in " ".join(texts(view))


def test_the_stage_dropdown_lists_the_stages_and_narrows_the_list(db, world, slack):
    create(world, "Design one", world["ravi"], stage="Design")
    create(world, "Sourcing one", world["ravi"], stage="Sourcing")

    home.publish("U0RAVI1234")
    home.publish("U0RAVI1234", stage="Sourcing")

    (_, everything), (_, narrowed) = slack["homes"]
    select = filter_select(everything, blocks.HOME_STAGE_ACTION)
    assert [o["text"]["text"] for o in select["options"]] == ["All stages", "Design", "Sourcing"]
    assert len(rows(everything)) == 2
    assert len(rows(narrowed)) == 1 and "Sourcing one" in rows(narrowed)[0]
    assert filter_select(narrowed, blocks.HOME_STAGE_ACTION)["initial_option"]["value"] == "Sourcing"


def filter_select(view, action_id):
    [select] = [e for b in view["blocks"] if b.get("block_id") == "wb_home_filter" for e in b["elements"] if e["action_id"] == action_id]
    return select


def test_the_show_dropdown_counts_each_status_and_narrows_the_list_to_one(db, world, slack):
    blocked = create(world, "Stuck", world["ravi"])
    create(world, "Waiting", world["ravi"])
    create(world, "Also waiting", world["ravi"])
    db.get(Task, uuid.UUID(blocked)).status = "blocked"
    db.commit()

    home.publish("U0RAVI1234")
    home.publish("U0RAVI1234", status="blocked")

    (_, everything), (_, only_blocked) = slack["homes"]
    show = filter_select(everything, blocks.HOME_STATUS_FILTER_ACTION)
    assert [o["text"]["text"] for o in show["options"]] == ["All (3)", "Blocked (1)", "In Progress (0)", "Review (0)", "To Do (2)", "Done (0)"]
    assert show["initial_option"]["value"] == blocks.HOME_ALL and len(rows(everything)) == 3
    assert len(rows(only_blocked)) == 1 and "Stuck" in rows(only_blocked)[0]
    assert filter_select(only_blocked, blocks.HOME_STATUS_FILTER_ACTION)["initial_option"]["value"] == "blocked"
    assert not any(t.startswith(blocks.STATUS_MARK["todo"]) for t in texts(only_blocked))  # the other groups are gone


def test_the_filters_are_remembered_across_redraws_and_choosing_all_clears_them(db, world, slack):
    create(world, "Design one", world["ravi"], stage="Design")
    create(world, "Sourcing one", world["ravi"], stage="Sourcing")

    home.publish("U0RAVI1234", stage="Design")
    home.publish("U0RAVI1234")  # e.g. a move redrew it, or the tab was opened again
    home.publish("U0RAVI1234", stage=None)

    (_, chosen), (_, redrawn), (_, cleared) = slack["homes"]
    assert len(rows(chosen)) == len(rows(redrawn)) == 1 and len(rows(cleared)) == 2


def test_a_filter_that_matches_nothing_says_so_and_keeps_the_dropdowns(db, world, slack):
    create(world, "Waiting", world["ravi"])

    home.publish("U0RAVI1234", status="review")

    [(_, view)] = slack["homes"]
    assert rows(view) == [] and any("No tasks match this filter" in t for t in texts(view))
    assert filter_select(view, blocks.HOME_STATUS_FILTER_ACTION)["initial_option"]["value"] == "review"


def test_a_long_list_is_cut_to_what_a_home_tab_can_hold_and_says_so(db, world, slack):
    for n in range(blocks.HOME_MAX_TASKS + 3):
        create(world, f"Task {n}", world["ravi"])

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    assert len(rows(view)) == blocks.HOME_MAX_TASKS and len(view["blocks"]) < 100
    assert any(f"Showing the first {blocks.HOME_MAX_TASKS} of {blocks.HOME_MAX_TASKS + 3} tasks" in t for t in texts(view))


def test_groups_have_a_coloured_square_and_dividers_separate_the_groups_and_tasks(db, world, slack):
    create(world, "First", world["ravi"])
    create(world, "Second", world["ravi"])

    home.publish("U0RAVI1234")

    [(_, view)] = slack["homes"]
    assert any(t.startswith(f"{blocks.STATUS_MARK['todo']}  *To Do*  (2)") for t in texts(view))
    kinds = [b["type"] for b in view["blocks"]]
    assert kinds.count("divider") == 1 + 1  # one above the group, one between its two tasks (none doubled up)
    assert any("Priority" in t and ":red_circle: High" in t for t in texts(view))  # the legend for the dots


def test_the_details_popup_shows_the_task_and_its_thread_oldest_first(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"], description="The jig is ready.", project="P1", stage="Design")
    world["directory"].call(world["asha"], "POST", f"/tasks/{task_id}/comments", json={"body": "Please start today."})
    assert interactions.move("U0RAVI1234", task_id, "blocked", "Waiting for steel") is None

    view, problem = interactions.details_view("U0RAVI1234", task_id)

    assert problem is None and view["type"] == "modal" and view["title"]["text"].startswith("Task #")
    text = " ".join(texts(view)) + " ".join(f["text"] for b in view["blocks"] for f in b.get("fields", []))
    assert "Design weld jig" in text and "The jig is ready." in text and "`P1`" in text and "`Design`" in text
    assert "Created the task" in text and "> Please start today." in text
    assert "Moved it to *Blocked*" in text and "> Waiting for steel" in text and "from Slack" in text
    assert text.index("Created the task") < text.index("Please start today.") < text.index("Waiting for steel")
    assert "> *Asha* · manager" in text and "> *Ravi* · you" in text  # each entry is a quote: a line down its side
    assert "square" not in text
    assert len(view["blocks"]) < 100


def test_the_details_popup_has_a_comment_box_that_saves_through_the_comment_form_handler(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"])

    view, _ = interactions.details_view("U0RAVI1234", task_id)

    assert view["callback_id"] == "wb_comment_submit" and view["private_metadata"] == task_id
    assert view["submit"]["text"] == "Comment" and view["close"]["text"] == "Close"
    box = view["blocks"][-1]
    assert (box["type"], box["block_id"], box["element"]["action_id"]) == ("input", "comment", "text")  # what the handler reads
    assert interactions.comment("U0RAVI1234", view["private_metadata"], "Parts arrived.") is None
    after, _ = interactions.details_view("U0RAVI1234", task_id)
    assert "> Parts arrived." in " ".join(texts(after))


def test_a_finished_task_has_no_comment_box(db, world, slack):
    task_id = create(world, "Done one", world["ravi"])
    db.get(Task, uuid.UUID(task_id)).status = "done"
    db.commit()

    view, _ = interactions.details_view("U0RAVI1234", task_id)

    assert "submit" not in view and view["blocks"][-1]["type"] != "input"


def test_only_the_assignee_may_open_a_tasks_details(db, world, slack):
    task_id = create(world, "Ravis task", world["ravi"])

    assert interactions.details_view("U0MEENA123", task_id)[0] is None
    assert interactions.details_view("U0NOBODY99", task_id)[1] == interactions.NOT_FOUND
    assert interactions.details_view("U0RAVI1234", "not-a-uuid")[1] == "That task could not be found."
    assert interactions.details_view("U0RAVI1234", str(uuid.uuid4()))[1] == "That task could not be found."


def test_a_person_with_nothing_open_and_a_stranger_each_get_a_plain_view(db, world, slack):
    home.publish("U0RAVI1234")
    home.publish("U0NOBODY99")

    (_, empty), (_, stranger) = slack["homes"]
    assert "Nothing open right now." in texts(empty) and rows(empty) == []
    assert "could not find you" in texts(stranger)[0]


def test_nothing_is_published_when_slack_is_not_set_up_and_a_slack_failure_is_swallowed(db, world, monkeypatch):
    sent = []
    monkeypatch.setattr(client, "publish_home", lambda *a: sent.append(a))
    home.publish("U0RAVI1234")  # settings.slack_bot_token is empty in tests
    assert sent == []

    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")

    def boom(*a):
        raise client.SlackError("Slack refused it: invalid_auth.")

    monkeypatch.setattr(client, "publish_home", boom)
    home.publish("U0RAVI1234")  # does not raise


def test_a_move_made_from_slack_redraws_the_home_tab(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"])
    slack["homes"].clear()

    assert interactions.move("U0RAVI1234", task_id, "in_progress", None) is None

    [(user, view)] = slack["homes"]
    assert user == "U0RAVI1234" and any("*In Progress*" in t for t in texts(view))


def test_a_refused_move_puts_the_home_tab_back(db, world, slack):
    task_id = create(world, "Design weld jig", world["ravi"])
    db.get(Task, uuid.UUID(task_id)).status = "done"
    db.commit()
    slack["homes"].clear()

    assert interactions.move("U0RAVI1234", task_id, "todo", "again") is not None

    assert [user for user, _ in slack["homes"]] == ["U0RAVI1234"]
