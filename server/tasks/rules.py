"""Calculated task facts (overdue, due soon, needs a new owner). Pure functions; `today` is passed in so tests do
not depend on the clock. Mirrors client/src/app/domain/permissions.ts.

shortcut: "today" is the server's calendar day, not each team's; fine for one office, revisit for several time zones.
"""
from datetime import date

from models import Person, Task

DUE_SOON_DAYS = 2
DUE_THIS_WEEK_DAYS = 6


def is_overdue(task: Task, today: date) -> bool:
    return task.due_at is not None and task.status != "done" and task.due_at < today


def _days_left(task: Task, today: date) -> int | None:
    """Whole days until the due date; None when there is no date, it has passed, or the task is done."""
    if task.due_at is None or task.status == "done" or task.due_at < today:
        return None
    return (task.due_at - today).days


def is_due_soon(task: Task, today: date) -> bool:
    days = _days_left(task, today)
    return days is not None and days <= DUE_SOON_DAYS


def is_due_this_week(task: Task, today: date) -> bool:
    days = _days_left(task, today)
    return days is not None and days <= DUE_THIS_WEEK_DAYS


def needs_reassignment(task: Task, assignee: Person | None) -> bool:
    """The owner is gone, inactive, or no longer on the task's team."""
    if task.status == "done":
        return False
    return assignee is None or not assignee.active or assignee.team_id != task.team_id


def needs_attention(task: Task, assignee: Person | None, today: date) -> bool:
    """What the manager has to act on: overdue, blocked, in Review or needing a new owner. Done never counts."""
    return task.status != "done" and (
        is_overdue(task, today) or task.status in ("blocked", "review") or needs_reassignment(task, assignee)
    )
