"""What a manager does with suggestions (edit, reject, restore, add to the board, expiry) and the list the page reads.
Suggestions are stored directly; the standup database is a fake. People and work are made up."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from core.config import settings
from core.exceptions import AppError
from models import Person, Task, TaskActivity, TaskSuggestion, Team
from standups.llm import extract
from standups.services import queries, suggestions as service, sync
from standups.standup_db import reader
from tests.conftest import make_team

TODAY = date.today()
LONG_AGO = datetime.now(timezone.utc) - timedelta(days=4)


@pytest.fixture
def world(directory, admin):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    return {"asha": asha, "ravi": ravi, "admin": admin, "team_id": uuid.UUID(team["id"]), "directory": directory}


@pytest.fixture
def make(db, world):
    count = {"n": 0}

    def _make(title=None, person=None, **over):
        count["n"] += 1
        title = title or f"Task number {count['n']} about something unique{count['n']}"
        values = dict(
            team_id=world["team_id"], person_id=(person or world["ravi"]).id, source_submission_id=1, standup_date=TODAY,
            title=title, title_key=extract.norm(title), description="It is done.", kind="new", priority="medium",
            evidence_quote="a line from the standup", model="m", prompt_hash="h", due_at=TODAY + timedelta(days=3),
        )
        s = TaskSuggestion(**{**values, **over})
        db.add(s)
        db.commit()
        return s
    return _make


def refetch(db, s):
    db.refresh(s)
    return s


# ---- edit ----

def test_editing_a_pending_suggestion_changes_it_and_a_new_date_is_no_longer_the_default(db, world, make):
    s = make(due_is_default=True)
    due = TODAY + timedelta(days=6)

    service.edit_suggestion(db, world["asha"], s.id, {
        "title": "  Build the weld jig  ", "description": "Jig built.", "priority": "high", "person_id": world["asha"].id, "due_at": due,
    })

    s = refetch(db, s)
    assert (s.title, s.title_key, s.description, s.priority, s.person_id) == (
        "Build the weld jig", "build the weld jig", "Jig built.", "high", world["asha"].id)
    assert (s.due_at, s.due_is_default) == (due, False)


@pytest.mark.parametrize("changes,code", [
    ({"title": "   "}, "invalid_title"),
    ({"description": ""}, "invalid_description"),
    ({"priority": "urgent"}, "invalid_priority"),
    ({"person_id": uuid.uuid4()}, "invalid_assignee"),
])
def test_an_invalid_edit_is_refused_and_changes_nothing(db, world, make, changes, code):
    s = make()

    with pytest.raises(AppError) as err:
        service.edit_suggestion(db, world["asha"], s.id, changes)

    assert (err.value.code, err.value.status_code) == (code, 422)
    assert refetch(db, s).title == s.title


def test_nobody_but_the_teams_manager_may_change_suggestions(db, world, make, directory):
    s = make()
    outsider = directory.person("Zoe")
    make_team(directory, world["admin"], "QA", outsider)

    for actor in (world["ravi"], world["admin"], outsider):
        for call in (service.reject_suggestion, service.restore_suggestion):
            with pytest.raises(AppError) as err:
                call(db, actor, s.id)
            assert err.value.status_code == 403
        with pytest.raises(AppError) as err:
            service.edit_suggestion(db, actor, s.id, {"priority": "low"})
        assert err.value.status_code == 403
        with pytest.raises(AppError) as err:
            service.add_to_board(db, actor, world["team_id"], [s.id])
        assert err.value.status_code == 403


def test_an_unknown_suggestion_is_a_404(db, world):
    with pytest.raises(AppError) as err:
        service.reject_suggestion(db, world["asha"], uuid.uuid4())
    assert (err.value.code, err.value.status_code) == ("suggestion_not_found", 404)


# ---- reject and restore ----

def test_a_rejected_suggestion_can_be_restored_for_three_days(db, world, make):
    fresh, old = make(), make()

    service.reject_suggestion(db, world["asha"], fresh.id)
    service.reject_suggestion(db, world["asha"], old.id)
    old.state_at = LONG_AGO
    db.commit()

    assert refetch(db, fresh).state == "rejected"
    service.restore_suggestion(db, world["asha"], fresh.id)
    assert refetch(db, fresh).state == "pending"
    with pytest.raises(AppError) as err:
        service.restore_suggestion(db, world["asha"], old.id)
    assert (err.value.code, err.value.status_code) == ("not_restorable", 409)


def test_a_rejected_suggestion_cannot_be_edited_or_rejected_again(db, world, make):
    s = make()
    service.reject_suggestion(db, world["asha"], s.id)

    for call in (lambda: service.reject_suggestion(db, world["asha"], s.id),
                 lambda: service.edit_suggestion(db, world["asha"], s.id, {"priority": "low"})):
        with pytest.raises(AppError) as err:
            call()
        assert err.value.code == "suggestion_not_pending"


# ---- add to the board ----

def test_adding_creates_a_task_for_each_suggestion_assigned_to_its_person(db, world, make):
    one = make("Design weld jig", priority="high", subtasks=["table", "mounting plate"], start_at=TODAY)
    two = make("Order bracket samples", person=world["asha"])

    service.add_to_board(db, world["asha"], world["team_id"], [one.id, two.id, one.id])  # a repeated id counts once

    tasks = {t.title: t for t in db.scalars(select(Task))}
    assert set(tasks) == {"Design weld jig", "Order bracket samples"}
    jig = tasks["Design weld jig"]
    assert (jig.assignee_id, jig.priority, jig.status, jig.creator_id, jig.start_at) == (world["ravi"].id, "high", "todo", world["asha"].id, TODAY)
    assert jig.description == "It is done.\n\nParts:\n- table\n- mounting plate"
    assert tasks["Order bracket samples"].assignee_id == world["asha"].id
    assert db.scalar(select(func.count()).select_from(TaskActivity)) == 2  # each task has its "created" entry
    assert [(refetch(db, s).state, s.task_id) for s in (one, two)] == [("approved", jig.id), ("approved", tasks["Order bracket samples"].id)]


def test_adding_is_all_or_nothing(db, world, make):
    good = make("Design weld jig")
    stale = make("Order bracket samples", due_at=TODAY - timedelta(days=2))  # a task cannot be due in the past

    with pytest.raises(AppError) as err:
        service.add_to_board(db, world["asha"], world["team_id"], [good.id, stale.id])

    assert "Order bracket samples" in err.value.message
    assert db.scalar(select(func.count()).select_from(Task)) == 0
    assert [refetch(db, s).state for s in (good, stale)] == ["pending", "pending"]

    service.edit_suggestion(db, world["asha"], stale.id, {"due_at": TODAY + timedelta(days=1)})
    service.add_to_board(db, world["asha"], world["team_id"], [good.id, stale.id])
    assert db.scalar(select(func.count()).select_from(Task)) == 2


def test_a_start_date_after_the_due_date_is_dropped_not_refused(db, world, make):
    s = make("Design weld jig", start_at=TODAY + timedelta(days=5), due_at=TODAY + timedelta(days=2))

    service.add_to_board(db, world["asha"], world["team_id"], [s.id])

    assert db.scalar(select(Task.start_at)) is None


def test_adding_refuses_what_is_gone_or_already_done_or_another_teams(db, world, make, directory):
    added, rejected = make(), make()
    service.add_to_board(db, world["asha"], world["team_id"], [added.id])
    service.reject_suggestion(db, world["asha"], rejected.id)
    zoe = directory.person("Zoe")
    qa = make_team(directory, world["admin"], "QA", zoe)

    for ids in ([added.id], [rejected.id]):
        with pytest.raises(AppError) as err:
            service.add_to_board(db, world["asha"], world["team_id"], ids)
        assert (err.value.code, err.value.status_code) == ("suggestion_not_pending", 409)
    for actor, team_id, ids in ((world["asha"], world["team_id"], [uuid.uuid4()]), (zoe, uuid.UUID(qa["id"]), [added.id])):
        with pytest.raises(AppError) as err:
            service.add_to_board(db, actor, team_id, ids)
        assert (err.value.code, err.value.status_code) == ("suggestion_not_found", 404)


# ---- expiry ----

def test_old_pending_and_rejected_suggestions_are_removed_but_approved_and_fresh_ones_stay(db, world, make):
    make(state="pending", state_at=LONG_AGO)
    make(state="rejected", state_at=LONG_AGO)
    old_approved, fresh = make(state="approved", state_at=LONG_AGO), make()
    kept = {old_approved.id, fresh.id}

    service.expire(db, world["team_id"])

    assert {s.id for s in db.scalars(select(TaskSuggestion))} == kept


# ---- the list the page reads ----

def submission(person, day=TODAY, this_week="- Start the weld jig design"):
    return reader.Submission(
        id=1, standup_date=day, person_name=person.name, email=person.email, slack_user_id=None, last_week="- done",
        this_week=this_week, blockers=None, combined=None, raw_content="raw", is_late_reply=False, source="bot",
    )


def test_the_list_has_each_person_with_their_latest_standup_and_recent_suggestions(db, world, make, monkeypatch):
    monkeypatch.setattr(queries.reader, "list_submissions", lambda channel, since: [
        submission(world["ravi"], TODAY - timedelta(days=7)), submission(world["ravi"], TODAY, "- newer"),
    ])
    mine = make(person=world["ravi"])
    make(person=world["ravi"], state="rejected", state_at=LONG_AGO)  # too old to show

    page = queries.list_for_team(db, world["asha"], world["team_id"])
    entries = page.people

    by_name = {e.person.name: e for e in entries}
    assert page.standup_problem is None
    assert [e.person.name for e in entries] == ["Asha", "Ravi"]  # the manager first
    assert by_name["Asha"].standup is None and by_name["Asha"].suggestions == []  # posted nothing
    assert by_name["Ravi"].standup.this_week == "- newer"
    assert [s.id for s in by_name["Ravi"].suggestions] == [mine.id]


def test_the_list_still_works_when_the_standup_database_is_not_set_up(db, world, make):
    make()  # no fake reader: the real one answers 501 standups_not_configured, which the list absorbs

    page = queries.list_for_team(db, world["asha"], world["team_id"])

    assert page.standup_problem == "not_configured"
    assert all(e.standup is None for e in page.people) and sum(len(e.suggestions) for e in page.people) == 1


def test_the_list_still_works_when_the_standup_database_cannot_be_opened(db, world, make, monkeypatch, tmp_path):
    make()
    monkeypatch.setattr(settings, "standup_db_url", f"sqlite:///{tmp_path / 'missing' / 'standup.db'}")  # a folder that is not there
    reader._engine.cache_clear()
    try:
        page = queries.list_for_team(db, world["asha"], world["team_id"])
    finally:
        reader._engine.cache_clear()

    assert page.standup_problem == "unreadable"  # not a 500, and not mistaken for "nobody posted"
    assert all(e.standup is None for e in page.people) and sum(len(e.suggestions) for e in page.people) == 1


def test_a_channel_with_no_posts_at_all_is_reported_so_a_wrong_channel_id_is_obvious(db, world, make, monkeypatch):
    monkeypatch.setattr(queries.reader, "list_submissions", lambda channel, since: [])

    page = queries.list_for_team(db, world["asha"], world["team_id"])

    assert page.standup_problem == "channel_empty" and all(e.standup is None for e in page.people)


def test_no_standup_channel_is_not_a_problem_just_nothing_to_read(db, world, make):
    team = db.get(Team, world["team_id"])
    team.standup_channel_id = None
    db.commit()

    assert queries.list_for_team(db, world["asha"], world["team_id"]).standup_problem is None


def test_who_may_read_the_list(db, world, directory):
    zoe = directory.person("Zoe")
    make_team(directory, world["admin"], "QA", zoe)

    assert len(queries.list_for_team(db, world["admin"], world["team_id"]).people) == 2  # an admin reads any team
    for actor in (zoe, world["ravi"]):
        with pytest.raises(AppError) as err:
            queries.list_for_team(db, actor, world["team_id"])
        assert err.value.status_code == 403


def test_last_synced_is_none_until_the_whole_team_is_read_and_is_set_even_when_no_standup_is_found(db, world, monkeypatch):
    monkeypatch.setattr(sync.reader, "list_submissions", lambda channel, since: [])  # nobody posted
    assert queries.last_synced(db, world["team_id"]) is None

    sync.sync_team(db, world["asha"], world["team_id"], world["ravi"].id)  # one person only: says nothing about the team
    assert queries.last_synced(db, world["team_id"]) is None

    sync.sync_team_scheduled(db, world["team_id"])  # the whole team, and nothing was found
    assert queries.last_synced(db, world["team_id"]) is not None
