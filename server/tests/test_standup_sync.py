"""The sync job: standup submissions of a team's own people in, stored suggestions out. The standup database and the
language model are both fakes; the people and work are made up."""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from core.config import settings
from core.exceptions import AppError
from models import Person, StandupRead, Task, TaskSuggestion, Team
from standups.llm import extract, prompt
from standups.services import sync
from standups.standup_db import reader
from tests.conftest import make_team

TODAY = date.today()
MONDAY = TODAY + timedelta(days=7 - TODAY.weekday())  # the next Monday, so the Friday default is never in the past
QUOTE = "Start the weld jig design for the rear axle"


def submission(sub_id=1, *, slack="U9999", email=None, this_week=f"- {QUOTE}", day=MONDAY, late=False):
    return reader.Submission(
        id=sub_id, standup_date=day, person_name="Whoever", email=email, slack_user_id=slack, last_week=None,
        this_week=this_week, blockers=None, combined=None, raw_content=this_week, is_late_reply=late, source="bot",
    )


def answer(*items):
    return {"items": list(items)}


def model_item(title="Design weld jig for rear axle", quote=QUOTE, **over):
    return {
        "title": title, "description": "The jig design is ready.", "kind": "new", "assignee": "Whoever", "due": None,
        "priority": "medium", "evidence_quote": quote, "subtasks": [], "related_to": None, **over,
    }


@pytest.fixture
def world(directory, admin, monkeypatch):
    """NPI (channel C0NPI) run by Asha with Ravi on it; a fake standup database and a fake model that count their calls."""
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    state = {"subs": [], "answers": [], "prompts": [], "channels": []}

    def list_submissions(channel, since):
        state["channels"].append((channel, since))
        return state["subs"]

    def complete_json(text, schema):
        state["prompts"].append(text)
        reply = state["answers"].pop(0) if state["answers"] else answer()
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(sync.reader, "list_submissions", list_submissions)
    monkeypatch.setattr(extract, "complete_json", complete_json)
    monkeypatch.setattr(settings, "llm_model", "test-model")
    return {"asha": asha, "ravi": ravi, "team": team, "admin": admin, "directory": directory, **state}


def run(world, actor=None):
    sync.sync_team(world["directory"].db, actor or world["asha"], uuid.UUID(world["team"]["id"]))


def stored(db):
    return list(db.scalars(select(TaskSuggestion).order_by(TaskSuggestion.created_at, TaskSuggestion.title)))


def test_a_team_members_standup_becomes_suggestions_with_the_friday_default(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id, late=True))  # matched by Slack id
    world["answers"].append(answer(model_item()))

    run(world)

    [s] = stored(db)
    assert (s.person_id, s.title, s.state, s.late_reply, s.model) == (world["ravi"].id, "Design weld jig for rear axle", "pending", True, "test-model")
    assert (s.due_at, s.due_is_default, s.start_at) == (MONDAY + timedelta(days=4), True, MONDAY)
    assert s.evidence_quote == QUOTE and s.prompt_hash == prompt.PROMPT_HASH and s.task_id is None
    assert world["channels"][0][0] == "C0TEST"
    assert "Submitter: Whoever" in world["prompts"][0]


def test_a_date_the_standup_states_is_used_as_it_is(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    stated = MONDAY + timedelta(days=2)
    world["answers"].append(answer(model_item(due=stated.isoformat())))

    run(world)

    assert [(s.due_at, s.due_is_default) for s in stored(db)] == [(stated, False)]


def test_a_stated_date_that_has_already_passed_is_not_kept(db, world):
    last_monday = TODAY - timedelta(days=TODAY.weekday() + 7)  # last week's standup, so its Wednesday and its Friday have both passed
    world["subs"].append(submission(slack=world["ravi"].slack_user_id, day=last_monday))
    world["answers"].append(answer(model_item(due=(last_monday + timedelta(days=2)).isoformat())))  # "by Wednesday", read a week later

    run(world)

    assert [(s.due_at, s.due_is_default) for s in stored(db)] == [(None, False)]  # a task cannot be due in the past


def test_a_stated_date_before_the_standup_itself_is_ignored_and_the_friday_default_applies(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))  # the standup is next Monday
    world["answers"].append(answer(model_item(due=(TODAY - timedelta(days=2)).isoformat())))  # a date from before it: a mistake

    run(world)

    assert [(s.due_at, s.due_is_default) for s in stored(db)] == [(MONDAY + timedelta(days=4), True)]


def test_a_stated_date_of_today_is_kept(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id, day=TODAY))  # a standup posted today, due today
    world["answers"].append(answer(model_item(due=TODAY.isoformat())))

    run(world)

    assert [(s.due_at, s.due_is_default) for s in stored(db)] == [(TODAY, False)]


def test_a_default_friday_that_has_passed_leaves_no_date(db, world):
    old = TODAY - timedelta(days=TODAY.weekday() + 7)  # last week's Monday: its Friday has gone
    world["subs"].append(submission(slack=world["ravi"].slack_user_id, day=old))
    world["answers"].append(answer(model_item()))

    run(world)

    assert [(s.due_at, s.due_is_default) for s in stored(db)] == [(None, False)]


def test_people_are_matched_by_email_when_the_slack_id_does_not_match_and_strangers_are_skipped(db, world):
    world["subs"] += [
        submission(1, slack="UNOPE", email="RAVI@atimotors.com"),
        submission(2, slack="UNOPE", email="stranger@example.org"),
    ]
    world["answers"] += [answer(model_item()), answer(model_item(title="Order bracket samples"))]

    run(world)

    assert [s.person_id for s in stored(db)] == [world["ravi"].id]
    assert len(world["prompts"]) == 1  # the stranger's standup never reached the model


def test_an_unchanged_submission_is_not_read_again_even_when_it_gave_nothing(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    world["answers"].append(answer())  # nothing worth tracking

    run(world)
    run(world)

    assert len(world["prompts"]) == 1 and stored(db) == []
    assert db.scalars(select(StandupRead)).one().content_hash


def test_an_edited_submission_is_read_again_and_only_new_suggestions_are_added(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    world["answers"].append(answer(model_item()))
    run(world)

    edited = f"- {QUOTE}\n- Review the test plan with Meena by Wednesday"
    world["subs"][:] = [submission(slack=world["ravi"].slack_user_id, this_week=edited)]
    world["answers"].append(answer(
        model_item(), model_item(title="Review test plan with Meena", quote="Review the test plan with Meena by Wednesday"),
    ))
    run(world)

    assert sorted(s.title for s in stored(db)) == ["Design weld jig for rear axle", "Review test plan with Meena"]
    assert len(world["prompts"]) == 2


def test_one_person_can_be_synced_alone_and_the_others_are_read_later(db, world):
    world["subs"] += [submission(1, slack=world["ravi"].slack_user_id), submission(2, slack=world["asha"].slack_user_id)]
    world["answers"] += [answer(model_item()), answer(model_item(title="Order bracket samples"))]
    team_id = uuid.UUID(world["team"]["id"])

    sync.sync_team(db, world["asha"], team_id, world["ravi"].id)

    assert len(world["prompts"]) == 1 and "Submitter: Whoever" in world["prompts"][0]
    assert [s.person_id for s in stored(db)] == [world["ravi"].id]
    assert [r.source_submission_id for r in db.scalars(select(StandupRead))] == [1]  # Asha's post is still unread

    sync.sync_team(db, world["asha"], team_id, world["asha"].id)

    assert len(world["prompts"]) == 2
    assert {s.person_id for s in stored(db)} == {world["ravi"].id, world["asha"].id}


def test_syncing_someone_who_is_not_on_the_team_is_a_404_and_reads_nothing(db, world, directory):
    outsider = directory.person("Zoe")
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))

    with pytest.raises(AppError) as err:
        sync.sync_team(db, world["asha"], uuid.UUID(world["team"]["id"]), outsider.id)

    assert (err.value.code, err.value.status_code) == ("person_not_on_team", 404)
    assert world["prompts"] == [] and world["channels"] == []


def old_row(db, world, person, title, state, day):
    row = TaskSuggestion(
        team_id=uuid.UUID(world["team"]["id"]), person_id=person.id, source_submission_id=900, standup_date=day, title=title,
        title_key=extract.norm(title), description="d", kind="new", priority="medium", evidence_quote="a line from it", state=state,
        model="m", prompt_hash="h",
    )
    db.add(row)
    db.commit()
    return row


def test_a_newer_standup_replaces_the_persons_older_suggestions_but_not_approved_ones_or_other_peoples(db, world):
    last_week = MONDAY - timedelta(days=7)
    for title, state in (("Old pending task", "pending"), ("Old rejected task", "rejected"), ("Old approved task", "approved")):
        old_row(db, world, world["ravi"], title, state, last_week)
    old_row(db, world, world["asha"], "Another persons old task", "pending", last_week)
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    world["answers"].append(answer(model_item()))

    run(world)

    assert sorted(s.title for s in stored(db)) == ["Another persons old task", "Design weld jig for rear axle", "Old approved task"]
    assert "Old pending task" not in world["prompts"][0]  # cleared before the model looked, so it cannot hide this week's work


def test_an_edit_to_the_same_standup_keeps_its_own_suggestions(db, world):
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    world["answers"].append(answer(model_item()))
    run(world)
    world["subs"][:] = [submission(slack=world["ravi"].slack_user_id, this_week=f"- {QUOTE}\n- and a new line about nothing")]
    world["answers"].append(answer())

    run(world)

    assert [s.title for s in stored(db)] == ["Design weld jig for rear axle"]


def test_a_failed_model_call_leaves_the_older_suggestions_alone(db, world):
    old_row(db, world, world["ravi"], "Old pending task", "pending", MONDAY - timedelta(days=7))
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    world["answers"].append(AppError("llm_failed", "down", 502))

    with pytest.raises(AppError):
        run(world)

    assert [s.title for s in stored(db)] == ["Old pending task"]


def test_the_prompt_lists_open_tasks_and_waiting_suggestions_but_not_done_work(db, world):
    team_id = world["team"]["id"]
    for title, status, owner in (("Order bracket samples", "in_progress", world["ravi"]), ("Old finished job", "done", world["ravi"])):
        db.add(Task(team_id=team_id, title=title, status=status, assignee_id=owner.id, creator_id=world["asha"].id))
    db.commit()
    world["subs"].append(submission(slack=world["ravi"].slack_user_id))
    world["answers"].append(answer(model_item()))

    run(world)

    sent = world["prompts"][0]
    assert "- Order bracket samples (In Progress, Ravi)" in sent and "Old finished job" not in sent

    world["subs"][:] = [submission(2, slack=world["asha"].slack_user_id)]
    world["answers"].append(answer())
    run(world)
    assert "- Design weld jig for rear axle (suggestion waiting, Ravi)" in world["prompts"][1]


def test_a_failed_model_call_keeps_earlier_work_and_is_tried_again(db, world):
    world["subs"] += [submission(1, slack=world["ravi"].slack_user_id), submission(2, slack=world["asha"].slack_user_id)]
    world["answers"] += [answer(model_item()), AppError("llm_failed", "down", 502)]

    with pytest.raises(AppError):
        run(world)

    assert len(stored(db)) == 1  # the first submission's work was committed before the second failed
    assert [r.source_submission_id for r in db.scalars(select(StandupRead))] == [1]  # the failed one is not marked read

    world["answers"].append(answer(model_item(title="Order bracket samples")))
    run(world)

    assert len(world["prompts"]) == 3 and len(stored(db)) == 2  # only the failed submission was sent again


def test_only_the_teams_own_manager_may_sync_and_the_team_needs_a_channel(db, world, directory):
    meena = directory.person("Meena")
    other = make_team(directory, world["admin"], "QA", directory.person("Zoe"))

    for actor in (world["ravi"], world["admin"], meena):
        with pytest.raises(AppError) as err:
            run(world, actor)
        assert err.value.status_code == 403

    qa = db.get(Team, uuid.UUID(other["id"]))
    qa.standup_channel_id = None
    db.commit()
    with pytest.raises(AppError) as err:
        sync.sync_team(db, db.get(Person, uuid.UUID(other["manager"]["id"])), qa.id)
    assert (err.value.code, err.value.status_code) == ("standup_channel_not_set", 409)
