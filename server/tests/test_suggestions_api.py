"""The suggestion endpoints end to end: sync, list, edit, reject, restore and add, with who may call each. The standup
database and the language model are fakes; the people and work are made up."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError

from core.config import settings
from models import Person, Task, TaskSuggestion
from standups.llm import extract
from standups.services import queries, sync
from standups.standup_db import reader
from standups.states import week_start
from tests.conftest import make_team

TODAY = date.today()
MONDAY = TODAY + timedelta(days=7 - TODAY.weekday())
QUOTE = "Start the weld jig design for the rear axle"


@pytest.fixture
def world(directory, admin, monkeypatch):
    asha, ravi = directory.person("Asha"), directory.person("Ravi")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    posts = [reader.Submission(
        id=1, standup_date=MONDAY, person_name="Ravi", email=ravi.email, slack_user_id=None, last_week="- Finished drawings",
        this_week=f"- {QUOTE}", blockers=None, combined=None, raw_content="raw", is_late_reply=False, source="bot",
        posted_at=datetime(2026, 11, 10, 4, 9, 21, tzinfo=timezone.utc),
    )]
    items = [{
        "title": "Design weld jig for rear axle", "description": "The jig design is ready.", "kind": "new",
        "assignee": "Ravi", "due": None, "priority": "medium", "evidence_quote": QUOTE, "subtasks": [], "related_to": None,
    }]
    for module in (sync.reader, queries.reader):
        monkeypatch.setattr(module, "list_submissions", lambda channel, since: posts)
    monkeypatch.setattr(extract, "complete_json", lambda text, schema: {"items": items})
    monkeypatch.setattr(settings, "llm_model", "test-model")
    return {"asha": asha, "ravi": ravi, "admin": admin, "team": team, "d": directory, "posts": posts}


def call(world, who, method, path, **kw):
    return world["d"].call(who, method, path, **kw)


def synced(world):
    res = call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/sync")
    assert res.status_code == 200, res.text
    return res.json()


def ravi_entry(page):
    return next(p for p in page["people"] if p["person"]["name"] == "Ravi")


def test_sync_returns_the_page_with_the_standup_blocks_and_the_new_suggestion(world):
    page = synced(world)

    assert page["standup_channel_id"] == "C0TEST" and page["last_synced_at"] is not None and page["standup_problem"] is None
    assert [p["person"]["name"] for p in page["people"]] == ["Asha", "Ravi"]
    asha, ravi = page["people"]
    assert asha["standup"] is None and asha["suggestions"] == []  # Asha posted nothing
    assert ravi["standup"] == {
        "date": MONDAY.isoformat(), "posted_at": "2026-11-10T04:09:21Z", "late_reply": False, "last_week": "- Finished drawings", "this_week": f"- {QUOTE}",
        "blockers": None, "message": None,
    }
    [s] = ravi["suggestions"]
    assert (s["title"], s["state"], s["priority"], s["person_id"], s["task_id"]) == (
        "Design weld jig for rear axle", "pending", "medium", str(world["ravi"].id), None)
    assert (s["due_at"], s["due_is_default"], s["evidence_quote"]) == ((MONDAY + timedelta(days=4)).isoformat(), True, QUOTE)


def test_a_post_with_no_sections_comes_back_as_one_message(world):
    world["posts"][0] = reader.Submission(**{**world["posts"][0].__dict__, "this_week": None, "last_week": None, "combined": "all in one"})

    page = call(world, world["asha"], "GET", f"/teams/{world['team']['id']}/suggestions").json()

    assert ravi_entry(page)["standup"] == {
        "date": MONDAY.isoformat(), "posted_at": "2026-11-10T04:09:21Z", "late_reply": False, "last_week": None, "this_week": None, "blockers": None, "message": "all in one",
    }


def test_the_standup_blocks_come_from_the_standup_database_and_need_no_sync_and_no_model(world, monkeypatch):
    def boom(text, schema):
        raise AssertionError("the model must not be called just to show the page")
    monkeypatch.setattr(extract, "complete_json", boom)

    page = call(world, world["asha"], "GET", f"/teams/{world['team']['id']}/suggestions").json()

    assert ravi_entry(page)["standup"]["this_week"] == f"- {QUOTE}" and ravi_entry(page)["suggestions"] == []


def test_the_page_shows_only_this_weeks_standups(world, monkeypatch):
    asked = []

    def recording(channel, since):
        asked.append(since)
        return world["posts"]

    monkeypatch.setattr(queries.reader, "list_submissions", recording)

    call(world, world["asha"], "GET", f"/teams/{world['team']['id']}/suggestions")

    assert asked == [week_start(TODAY)]  # this week's Monday: an earlier week's post is never asked for, so never shown


def test_a_standup_database_that_cannot_be_read_is_reported_not_a_500_or_a_silent_empty_page(world, monkeypatch):
    def unreadable(channel, since):
        raise OperationalError("select", {}, Exception("unable to open database file"))
    monkeypatch.setattr(queries.reader, "list_submissions", unreadable)

    res = call(world, world["asha"], "GET", f"/teams/{world['team']['id']}/suggestions")

    assert res.status_code == 200 and res.json()["standup_problem"] == "unreadable"
    assert all(p["standup"] is None for p in res.json()["people"])


def test_the_list_needs_no_sync_and_an_admin_may_read_it(world):
    team_id = world["team"]["id"]

    assert call(world, world["asha"], "GET", f"/teams/{team_id}/suggestions").status_code == 200
    res = call(world, world["admin"], "GET", f"/teams/{team_id}/suggestions")
    assert res.status_code == 200 and res.json()["last_synced_at"] is None


def test_edit_reject_restore_and_add_a_suggestion_end_to_end(world, db):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    due = (TODAY + timedelta(days=9)).isoformat()

    edited = call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json={"priority": "high", "due_at": due, "title": "Build weld jig"})
    assert edited.status_code == 200
    assert (edited.json()["priority"], edited.json()["due_at"], edited.json()["due_is_default"], edited.json()["title"]) == ("high", due, False, "Build weld jig")

    rejected = call(world, world["asha"], "POST", f"/suggestions/{sid}/reject")
    assert rejected.json()["state"] == "rejected"
    assert call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json={"priority": "low"}).json()["detail"]["code"] == "suggestion_not_pending"
    assert call(world, world["asha"], "POST", f"/suggestions/{sid}/restore").json()["state"] == "pending"

    added = call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/add", json={"suggestion_ids": [sid]})
    assert added.status_code == 200, added.text
    [s] = ravi_entry(added.json())["suggestions"]
    assert s["state"] == "approved" and s["task_id"] is not None
    task = db.scalar(select(Task))
    assert (str(task.id), task.title, task.priority, task.assignee_id, task.due_at.isoformat()) == (s["task_id"], "Build weld jig", "high", world["ravi"].id, due)


def test_adding_with_a_broken_task_rule_adds_nothing_and_names_the_suggestion(world, db):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    stale = db.get(TaskSuggestion, uuid.UUID(sid))  # a date that was fine when stored and has since passed
    stale.due_at = TODAY - timedelta(days=1)
    db.commit()

    res = call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/add", json={"suggestion_ids": [sid]})

    assert res.status_code == 422 and res.json()["detail"]["code"] == "due_date_past"
    assert "Design weld jig for rear axle" in res.json()["detail"]["message"]
    assert db.scalar(select(func.count()).select_from(Task)) == 0


def test_adding_a_suggestion_with_no_due_date_is_refused_by_the_server_until_a_date_is_sent(world, db):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    # The fixture's standup is next Monday, so move the start back with the due date before clearing it.
    assert call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json={"start_at": TODAY.isoformat(), "due_at": None}).status_code == 200
    add = lambda body: call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/add", json=body)  # noqa: E731

    refused = add({"suggestion_ids": [sid]})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "due_date_required")
    assert "Design weld jig for rear axle" in refused.json()["detail"]["message"]
    assert db.scalar(select(func.count()).select_from(Task)) == 0

    due = (TODAY + timedelta(days=5)).isoformat()
    ok = add({"suggestion_ids": [sid], "due_dates": {sid: due}})
    assert ok.status_code == 200
    assert db.scalar(select(Task)).due_at.isoformat() == due


def test_adding_a_suggestion_for_someone_who_left_the_team_is_a_named_422_not_a_500(world, db):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    db.execute(update(Person).where(Person.id == world["ravi"].id).values(team_id=None))  # removed from the team after the sync
    db.commit()
    db.expire_all()
    due = (TODAY + timedelta(days=5)).isoformat()

    res = call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/add", json={"suggestion_ids": [sid], "due_dates": {sid: due}})

    assert res.status_code == 422, (res.status_code, res.text)
    assert res.json()["detail"]["code"] == "invalid_assignee"
    assert "Design weld jig for rear axle" in res.json()["detail"]["message"] and "Ravi" in res.json()["detail"]["message"]
    assert db.scalar(select(func.count()).select_from(Task)) == 0


def test_a_due_date_cannot_be_chosen_in_the_past_but_today_and_clearing_are_fine(world):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    edit = lambda body: call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json=body)  # noqa: E731

    past = edit({"due_at": (TODAY - timedelta(days=1)).isoformat()})
    assert (past.status_code, past.json()["detail"]["code"]) == (422, "due_date_past")
    # The fixture's standup is next Monday, so its start date is later than today: move the start back with the due date.
    assert edit({"start_at": TODAY.isoformat(), "due_at": TODAY.isoformat()}).status_code == 200
    cleared = edit({"due_at": None})
    assert cleared.status_code == 200 and cleared.json()["due_at"] is None and cleared.json()["due_is_default"] is False


def test_a_start_date_cannot_be_after_the_due_date(world):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    due = (TODAY + timedelta(days=3)).isoformat()

    res = call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json={"start_at": (TODAY + timedelta(days=5)).isoformat(), "due_at": due})

    assert (res.status_code, res.json()["detail"]["code"]) == (422, "start_after_due")


def test_sync_can_be_limited_to_one_person(world):
    team_id = world["team"]["id"]

    asha_only = call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/sync?person_id={world['asha'].id}")
    assert asha_only.status_code == 200 and ravi_entry(asha_only.json())["suggestions"] == []  # Ravi's post was not read

    ravi_only = call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/sync?person_id={world['ravi'].id}")
    assert len(ravi_entry(ravi_only.json())["suggestions"]) == 1

    stranger = call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/sync?person_id={uuid.uuid4()}")
    assert (stranger.status_code, stranger.json()["detail"]["code"]) == (404, "person_not_on_team")
    assert call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/sync?person_id=nope").status_code == 422


def test_a_second_sync_adds_nothing_new(world):
    synced(world)
    page = synced(world)

    assert len(ravi_entry(page)["suggestions"]) == 1


def test_bad_requests_are_422(world):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    team_id = world["team"]["id"]

    assert call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/add", json={"suggestion_ids": []}).status_code == 422
    assert call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/add", json={}).status_code == 422
    assert call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json={"priority": "urgent"}).json()["detail"]["code"] == "invalid_priority"
    assert call(world, world["asha"], "PATCH", f"/suggestions/{sid}", json={"title": "x" * 141}).status_code == 422
    assert call(world, world["asha"], "PATCH", "/suggestions/not-a-uuid", json={}).status_code == 422
    assert call(world, world["asha"], "PATCH", f"/suggestions/{uuid.uuid4()}", json={}).status_code == 404


def test_a_person_can_sync_three_times_a_minute_and_the_fourth_is_a_429_that_costs_the_rest_nothing(world):
    from security import rate_limit

    assert rate_limit.SYNC_PER_MINUTE == 3  # the model costs money: three a minute, whole team or one person at a time
    team_id = world["team"]["id"]
    sync_path = f"/teams/{team_id}/suggestions/sync"

    codes = [call(world, world["asha"], "POST", sync_path).status_code for _ in range(4)]

    assert codes == [200, 200, 200, 429]
    assert call(world, world["asha"], "GET", f"/teams/{team_id}/suggestions").status_code == 200  # reading the page is not a sync
    assert call(world, world["admin"], "POST", sync_path).status_code == 200  # an admin has a budget of their own


def test_syncing_one_person_at_a_time_uses_the_same_budget(world):
    team_id = world["team"]["id"]

    codes = [call(world, world["asha"], "POST", f"/teams/{team_id}/suggestions/sync?person_id={p}").status_code
             for p in (world["asha"].id, world["ravi"].id, world["asha"].id, world["ravi"].id)]

    assert codes == [200, 200, 200, 429]


def test_the_scheduled_sync_is_not_counted_against_anyones_budget(world, db):
    from security import rate_limit

    rate_limit.check(("sync", world["asha"].id), 3, 60)
    rate_limit.check(("sync", world["asha"].id), 3, 60)
    rate_limit.check(("sync", world["asha"].id), 3, 60)  # Asha's budget is spent

    sync.sync_team_scheduled(db, uuid.UUID(world["team"]["id"]))  # the server's own run has no person and no limit

    assert call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/sync").status_code == 429


def test_an_admin_sync_stores_suggestions_for_the_manager_but_creates_no_task(world, db):
    team_id = world["team"]["id"]

    res = call(world, world["admin"], "POST", f"/teams/{team_id}/suggestions/sync")

    assert res.status_code == 200
    assert ravi_entry(res.json())["suggestions"][0]["state"] == "pending"  # waiting for the manager
    assert db.scalar(select(func.count()).select_from(Task)) == 0
    assert res.json()["last_synced_at"] is not None


def test_who_may_call_what(world, directory):
    sid = ravi_entry(synced(world))["suggestions"][0]["id"]
    team_id = world["team"]["id"]
    zoe = directory.person("Zoe")
    make_team(directory, world["admin"], "QA", zoe)
    calls = [
        ("GET", f"/teams/{team_id}/suggestions", None),
        ("POST", f"/teams/{team_id}/suggestions/sync", None),
        ("POST", f"/teams/{team_id}/suggestions/add", {"suggestion_ids": [sid]}),
        ("PATCH", f"/suggestions/{sid}", {"priority": "low"}),
        ("POST", f"/suggestions/{sid}/reject", None),
        ("POST", f"/suggestions/{sid}/restore", None),
    ]
    reads_ok = {"admin": {"GET"}}  # an admin reads another team's page ...

    for method, path, body in calls:
        kw = {"json": body} if body is not None else {}
        assert call(world, None, method, path, **kw).status_code == 401, path
        for name, who in (("ravi", world["ravi"]), ("zoe", zoe), ("admin", world["admin"])):
            admin_syncs = name == "admin" and path.endswith("/sync")  # ... and may sync it, but changes nothing else
            expected = 200 if method in reads_ok.get(name, set()) or admin_syncs else 403
            assert call(world, who, method, path, **kw).status_code == expected, (name, path)


def test_a_team_without_a_channel_cannot_sync(world, db):
    call(world, world["admin"], "PATCH", f"/teams/{world['team']['id']}/standup-channel", json={"standup_channel_id": None, "reason": "none"})

    res = call(world, world["asha"], "POST", f"/teams/{world['team']['id']}/suggestions/sync")

    assert res.status_code == 409 and res.json()["detail"]["code"] == "standup_channel_not_set"
