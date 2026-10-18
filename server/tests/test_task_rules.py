"""Task permission and transition rules (security/authorization.py). Pure functions, no database.
Mirrors client/src/app/domain/permissions.ts: change both together."""
import pytest

from models import Person, Team
from security.authorization import (
    can_act,
    can_comment,
    can_delete_task,
    can_view_team,
    transition_to,
    transitions_for,
)

STATUSES = ("todo", "in_progress", "blocked", "review", "done")


def person(**fields) -> Person:
    import uuid

    return Person(id=uuid.uuid4(), name="P", email="p@atimotors.com", slack_user_id="S", **fields)


@pytest.fixture
def manager():
    return person(role="manager")


@pytest.fixture
def team(manager):
    return Team(name="NPI", manager_id=manager.id)


def test_only_the_teams_manager_acts_an_admin_only_reads(manager, team):
    admin, other_manager = person(is_admin=True), person(role="manager")

    assert can_act(manager, team) and can_view_team(manager, team)
    assert can_view_team(admin, team) and not can_act(admin, team)
    assert not can_view_team(other_manager, team) and not can_act(other_manager, team)


def test_an_admin_who_runs_the_team_acts_on_it(team):
    admin_manager = person(is_admin=True, role="manager")
    own = Team(name="QA", manager_id=admin_manager.id)

    assert can_act(admin_manager, own)
    assert not can_act(admin_manager, team)


@pytest.mark.parametrize(
    "status, expected",
    [
        ("todo", {"in_progress", "blocked"}),
        ("in_progress", {"review", "done", "blocked", "todo"}),
        ("blocked", {"in_progress", "done", "todo"}),
        ("review", {"done", "in_progress"}),
        ("done", {"in_progress"}),
    ],
)
def test_the_moves_each_status_allows(manager, team, status, expected):
    assert {t.to for t in transitions_for(manager, team, status)} == expected


def test_no_one_but_the_manager_gets_any_move(team):
    assert transitions_for(person(is_admin=True), team, "todo") == []


def test_every_road_into_done_and_every_step_back_needs_a_reason(manager, team):
    for status in STATUSES:
        for t in transitions_for(manager, team, status):
            if t.to == "done" or t.kind in {"block", "move_back", "send_back", "reopen"}:
                assert t.needs_reason, (status, t)
    assert not transition_to(manager, team, "todo", "in_progress").needs_reason


def test_a_move_that_is_not_listed_is_not_a_transition(manager, team):
    assert transition_to(manager, team, "todo", "done") is None
    assert transition_to(manager, team, "review", "todo") is None


def test_delete_only_while_to_do_or_in_progress(manager, team):
    assert [s for s in STATUSES if can_delete_task(manager, team, s)] == ["todo", "in_progress"]
    assert not can_delete_task(person(is_admin=True), team, "todo")


def test_comments_on_anything_not_done(manager, team):
    assert [s for s in STATUSES if can_comment(manager, team, s)] == ["todo", "in_progress", "blocked", "review"]
    assert can_comment(person(is_admin=True), team, "todo")  # an admin may comment on any team's task...
    assert not can_comment(person(is_admin=True), team, "done")  # ...until it is Done
    assert not can_comment(person(), team, "todo")  # a plain person who runs no team may not
