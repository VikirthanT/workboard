"""Overdue, due soon and needs-a-new-owner (tasks/rules.py). Pure functions, no database."""
import uuid
from datetime import date, timedelta

from models import Person, Task
from tasks import rules

TODAY = date(2026, 10, 17)


def task(**fields) -> Task:
    defaults = {"team_id": uuid.uuid4(), "title": "t", "status": "todo"}
    return Task(**{**defaults, **fields})


def test_overdue_needs_a_past_date_and_an_open_task():
    assert rules.is_overdue(task(due_at=date(2026, 10, 16)), TODAY)
    assert not rules.is_overdue(task(due_at=TODAY), TODAY)  # due today is not late yet
    assert not rules.is_overdue(task(due_at=None), TODAY)
    assert not rules.is_overdue(task(due_at=date(2026, 10, 1), status="done"), TODAY)


def test_due_soon_is_today_through_two_days_out_and_due_this_week_through_six():
    def in_days(n: int) -> Task:
        return task(due_at=TODAY + timedelta(days=n))

    assert [rules.is_due_soon(in_days(n), TODAY) for n in (0, 2, 3)] == [True, True, False]
    assert [rules.is_due_this_week(in_days(n), TODAY) for n in (0, 6, 7)] == [True, True, False]
    assert not rules.is_due_soon(in_days(-1), TODAY)  # already late is overdue, not "soon"
    assert not rules.is_due_soon(task(due_at=TODAY, status="done"), TODAY)


def test_a_task_needs_a_new_owner_when_its_assignee_is_gone_inactive_or_elsewhere():
    team_id = uuid.uuid4()
    here = Person(team_id=team_id, active=True)
    t = task(team_id=team_id)

    assert not rules.needs_reassignment(t, here)
    assert rules.needs_reassignment(t, None)
    assert rules.needs_reassignment(t, Person(team_id=team_id, active=False))
    assert rules.needs_reassignment(t, Person(team_id=uuid.uuid4(), active=True))
    assert rules.needs_reassignment(t, Person(team_id=None, active=True))
    assert not rules.needs_reassignment(task(team_id=team_id, status="done"), None)  # finished work needs no owner


def test_attention_is_overdue_blocked_review_or_ownerless_and_never_done():
    team_id = uuid.uuid4()
    here = Person(team_id=team_id, active=True)
    quiet = task(team_id=team_id, due_at=TODAY + timedelta(days=5))

    assert not rules.needs_attention(quiet, here, TODAY)
    assert rules.needs_attention(task(team_id=team_id, due_at=date(2026, 10, 1)), here, TODAY)
    assert rules.needs_attention(task(team_id=team_id, status="blocked"), here, TODAY)
    assert rules.needs_attention(task(team_id=team_id, status="review"), here, TODAY)
    assert rules.needs_attention(quiet, None, TODAY)
    assert not rules.needs_attention(task(team_id=team_id, status="done", due_at=date(2026, 10, 1)), None, TODAY)
