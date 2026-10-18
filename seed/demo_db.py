#!/usr/bin/env python3
"""Load a demo world into the DEVELOPMENT database: Admin, Manager 1 and Manager 2 (who can sign in), two teams with
people, and 14 tasks in every state (overdue, blocked, in review, sent back, done, an owner who left).

    server/.venv/bin/python seed/demo_db.py [--reset | --remove]    (or: make db-demo, db-demo-reset, db-demo-remove)

Development only: it refuses to run unless DEV_AUTH is on, and the production image does not contain it. The demo
accounts have Slack ids starting with DEMO- so the directory load (make db-seed) leaves them alone. Teams are made
through the real services (so the audit log fills in); tasks are written with back-dated timelines, which the
services cannot do. Safe to run again: it skips if the demo is already there. --reset removes the demo people,
their teams and tasks, then loads it again; --remove only removes. Other people, teams and tasks are never touched.
It lives in the database volume, so `make dev-down` keeps it; only removing the volume (docker compose down -v)
wipes it along with everything else. The audit entries it made stay (the audit log is append-only).
"""
import argparse
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from core.config import settings  # noqa: E402
from database.config import SessionLocal  # noqa: E402
from identity import states  # noqa: E402
from identity.services import members, teams  # noqa: E402
from models import Person, Task, TaskActivity, Team  # noqa: E402

# key, name, email. The members' emails say demo so they can never clash with a real colleague's address.
PEOPLE = [
    ("admin", "Admin", "admin@atimotors.com"),
    ("manager1", "Manager 1", "manager1@atimotors.com"),
    ("manager2", "Manager 2", "manager2@atimotors.com"),
    ("aarav", "Aarav Menon", "demo.aarav@atimotors.com"),
    ("meera", "Meera Pillai", "demo.meera@atimotors.com"),
    ("rohan", "Rohan Shetty", "demo.rohan@atimotors.com"),
    ("sana", "Sana Qureshi", "demo.sana@atimotors.com"),
    ("ishaan", "Ishaan Rao", "demo.ishaan@atimotors.com"),
    ("divya", "Divya Nair", "demo.divya@atimotors.com"),
]
# team key, name, manager key, member keys
TEAMS = [
    ("npi", "NPI", "manager1", ["aarav", "meera", "rohan", "sana"]),
    ("val", "Validation", "manager2", ["ishaan", "divya"]),
]
LEFT = {"sana"}  # on the team, but no longer in the directory: their open task needs a new owner
MANAGER_OF = {team: manager for team, _, manager, _ in TEAMS}

# key, team, title, description, assignee, priority, due (days from today), created (days from today), steps.
# A step is (status moved to, days from today, reason or remarks). Every move is made by the team's manager.
TASKS = [
    ("t1", "npi", "Migrate telemetry ingest to the new queue", "Move the vehicle telemetry consumer off the legacy broker. Keep the old topic running until the dashboards are verified.",
     "aarav", "high", 3, -9, [("in_progress", -8), ("review", -1)]),
    ("t2", "npi", "Fix flaky CAN-bus parser tests", "Intermittent failures on CI since the parser refactor. Likely a timing assumption in the fixtures.",
     "aarav", "medium", -2, -12, [("in_progress", -10), ("blocked", -6, "CI runners are queued behind the release build; cannot reproduce locally.")]),
    ("t3", "npi", "Write onboarding notes for the diagnostics service", "Short doc: architecture, how to run locally, who to ask.",
     "meera", "low", 9, -2, []),
    ("t4", "npi", "Add retry + backoff to firmware update client", "OTA client gives up after one failed chunk. Needs bounded retries with jitter.",
     "meera", "high", 1, -7, [("in_progress", -6), ("review", -3), ("in_progress", -2, "Backoff ceiling is too aggressive for field units on 2G; please cap at 30s and add a test."), ("review", 0)]),
    ("t5", "npi", "Audit logging for admin API", "Every admin mutation must write who / what / old -> new.",
     "rohan", "medium", 5, -5, [("in_progress", -4)]),
    ("t6", "npi", "Upgrade build image to Node 22", "",
     "rohan", "low", -9, -20, [("in_progress", -18), ("review", -14), ("done", -12, "Verified the build on CI; image is live.")]),
    ("t7", "npi", "Document the release checklist", "Sync with QA on the final gate list.",
     "rohan", "low", -1, -6, []),
    ("t8", "npi", "Write the OTA rollback test plan", "",
     "meera", "medium", 4, -2, [("in_progress", -1)]),
    ("t14", "npi", "Compile field-test feedback", "The assignee has left; this still needs an owner.",
     "sana", "medium", 2, -5, [("in_progress", -4)]),
    ("t9", "val", "Validate BMS thermal limits on pack rev C", "Run the hot-soak profile and compare against the cell datasheet.",
     "ishaan", "high", -3, -14, [("in_progress", -13), ("blocked", -5, "Thermal chamber is booked until Friday; asked facilities for a slot.")]),
    ("t10", "val", "Order replacement connectors for the harness", "Part numbers are in the BOM; need quotes from two suppliers.",
     "divya", "medium", 4, -3, [("in_progress", -2)]),
    ("t11", "val", "Review harness drawing rev B", "",
     "divya", "medium", 2, -4, [("in_progress", -3), ("review", -1)]),
    ("t12", "val", "Calibrate current sensor test rig", "",
     "ishaan", "high", 1, -8, [("in_progress", -7), ("review", -2)]),
    ("t13", "val", "Clean up the lab test-bench inventory", "",
     "ishaan", "low", -4, -15, [("in_progress", -14), ("review", -9), ("done", -3, "Counts match the lab sheet.")]),
]
# task key, days from today, text. Written by the team's manager.
COMMENTS = [
    ("t1", -2, "Good. Please keep the old topic until Friday."),
    ("t2", -5, "Reproduced once on the shared runner, not locally."),
    ("t9", -4, "Facilities confirmed the chamber frees up Friday."),
    ("t11", -1, "Rev B drawing attached in the shared drive for review."),
]


def _is_demo():
    return Person.slack_user_id.like(f"{states.DEMO_SLACK_PREFIX}%")


def reset_demo(db: Session) -> None:
    """Remove the demo people, the teams they are on (which erases those teams' tasks and timelines)."""
    team_ids = db.scalars(select(Person.team_id).where(_is_demo(), Person.team_id.is_not(None))).unique().all()
    if team_ids:
        db.execute(delete(Team).where(Team.id.in_(team_ids)))
    db.execute(delete(Person).where(_is_demo()))
    db.commit()


def load_demo(db: Session, today: date | None = None) -> str:
    """Returns what happened, in a sentence. Never raises for 'already there' or 'name taken'."""
    today = today or date.today()
    if db.scalar(select(Person.id).where(_is_demo()).limit(1)) is not None:
        return "Demo data is already loaded (python seed/demo_db.py --reset loads it again)."
    taken_emails = db.scalars(select(Person.email).where(Person.email.in_([email for *_, email in PEOPLE]))).all()
    taken_teams = db.scalars(select(Team.name).where(func.lower(Team.name).in_([name.lower() for _, name, *_ in TEAMS]))).all()
    if taken_emails or taken_teams:
        return f"Demo data not loaded: these already exist: {', '.join(sorted(taken_emails + taken_teams))}."

    db.add_all(
        Person(slack_user_id=f"{states.DEMO_SLACK_PREFIX}{key}", email=email, name=name, is_admin=key == "admin")
        for key, name, email in PEOPLE
    )
    db.commit()
    ids = {key: db.scalar(select(Person.id).where(Person.slack_user_id == f"{states.DEMO_SLACK_PREFIX}{key}")) for key, *_ in PEOPLE}
    admin = db.get(Person, ids["admin"])

    team_ids = {}
    for key, name, manager, people in TEAMS:
        team_ids[key] = uuid.uuid4()
        teams.create_team(db, admin, team_ids[key], name, ids[manager], "Demo data")
        for person in people:
            members.add_member(db, admin, team_ids[key], ids[person], None)
    for key in LEFT:
        db.get(Person, ids[key]).active = False
    db.commit()

    _write_tasks(db, today, ids, team_ids)
    return f"Demo data loaded: sign in as Admin, Manager 1 or Manager 2 ({len(TASKS)} tasks on 2 teams)."


def _write_tasks(db: Session, today: date, ids: dict, team_ids: dict) -> None:
    def when(days: int, order: int = 0) -> datetime:
        return datetime.combine(today + timedelta(days=days), time(9, 0), tzinfo=timezone.utc) + timedelta(minutes=5 * order)

    tasks, entries = {}, []
    for key, team, title, description, assignee, priority, due, created, steps in TASKS:
        manager_id = ids[MANAGER_OF[team]]
        task = Task(
            id=uuid.uuid4(), team_id=team_ids[team], title=title, description=description, priority=priority,
            due_at=today + timedelta(days=due), creator_id=manager_id, assignee_id=ids[assignee],
            created_at=when(created), updated_at=when(created), returned_count=0, status="todo",
        )
        tasks[key] = task

        def entry(kind, at, **fields):
            entries.append(TaskActivity(task_id=task.id, actor_id=manager_id, kind=kind, created_at=at, **fields))

        entry("created", when(created), new_value="todo")
        for order, (to, days, *note) in enumerate(steps, start=1):
            if task.status == "review" and to == "in_progress":
                task.returned_count += 1  # a send back
            entry("status", when(days, order), field="status", old_value=task.status, new_value=to, note=note[0] if note else None)
            task.status, task.updated_at = to, when(days, order)
            task.closed_at = when(days, order) if to == "done" else None

    for key, days, text in COMMENTS:
        task = tasks[key]
        entries.append(TaskActivity(task_id=task.id, actor_id=ids[MANAGER_OF[task_team(key)]], kind="comment", note=text, created_at=when(days, 9)))
        task.updated_at = max(task.updated_at, when(days, 9))

    db.add_all(tasks.values())
    db.flush()  # the timeline rows point at the tasks
    db.add_all(entries)
    db.commit()


def task_team(key: str) -> str:
    return next(team for k, team, *_ in TASKS if k == key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--reset", action="store_true", help="remove the demo data first, then load it again")
    parser.add_argument("--remove", action="store_true", help="remove the demo data and stop")
    args = parser.parse_args(argv)
    if not settings.dev_auth:
        sys.exit("Demo data is for development only (DEV_AUTH is off), so nothing was loaded or removed.")
    with SessionLocal() as db:
        if args.remove:
            reset_demo(db)
            print("Demo data removed. (The audit log keeps its entries: it is append-only.)")
            return 0
        if args.reset:
            reset_demo(db)
        print(load_demo(db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
