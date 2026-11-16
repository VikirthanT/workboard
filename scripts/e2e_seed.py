#!/usr/bin/env python3
"""Add what the end-to-end tests need beyond the demo world: a few standup suggestions for the NPI team. Used by
scripts/test_all.py (make e2e), after seed/demo_db.py, on the throwaway database only.

    server/.venv/bin/python scripts/e2e_seed.py

Suggestions normally come from a sync, which needs the standup database and a language model; the throwaway server has
neither, so the rows are written directly, the way a sync would leave them: pending, from this week's standup. One has a
due date and one has none, so a test can show that adding needs a date. The text is made up.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from sqlalchemy import select  # noqa: E402

from database.config import SessionLocal  # noqa: E402
from models import Person, Team, TaskSuggestion  # noqa: E402
from standups.llm.extract import norm  # noqa: E402
from standups.states import week_start  # noqa: E402

# title, assignee email, days from today until due (None: the suggestion has no due date), priority
SUGGESTIONS = [
    ("E2E suggestion with a date", "demo.aarav@atimotors.com", 4, "high"),
    ("E2E suggestion without a date", "demo.meera@atimotors.com", None, "medium"),
]


def main() -> int:
    today = date.today()
    with SessionLocal() as db:
        team = db.scalar(select(Team).where(Team.name == "NPI"))
        if team is None:
            print("The demo world is not loaded: no NPI team.")
            return 1
        for index, (title, email, days, priority) in enumerate(SUGGESTIONS, start=9001):
            person = db.scalar(select(Person).where(Person.email == email))
            db.add(TaskSuggestion(
                team_id=team.id, person_id=person.id, source_submission_id=index, standup_date=week_start(today),
                title=title, title_key=norm(title), description="Made up for the end-to-end test.", kind="new", priority=priority,
                evidence_quote="a line from the standup", model="e2e", prompt_hash="e2e",
                due_at=None if days is None else today + timedelta(days=days),
            ))
        db.commit()
    print(f"Added {len(SUGGESTIONS)} suggestions to NPI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
