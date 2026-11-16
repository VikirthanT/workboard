#!/usr/bin/env python3
"""Write a small, made-up standup database for a team that already exists in the DEVELOPMENT database, so Suggestions
can be tried end to end without the real standup data.

    server/.venv/bin/python seed/demo_standup_db.py [--team NPI] [--path seed/demo-standup.db]    (or: make db-demo-standup)

It reads the team's people (name, email, Slack id) from the dev database and writes a SQLite file shaped like the standup
app's (channels, persons, standups, submissions): this week's standup and last week's for each person, with a
blocker, a late reply and a quiet week among them. The text is invented, nothing here is a real standup. If the team has
no standup channel yet it gives it one (through the real service, so the audit log shows it). The file is gitignored and
only ever replaced if it is one this script made.

Development only: it refuses to run unless DEV_AUTH is on. Then point the API at the file (in .env):
    STANDUP_DB_URL=sqlite:////<repo>/seed/demo-standup.db    (the script prints the exact line)
"""
import argparse
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from sqlalchemy import func, select  # noqa: E402

from core.config import settings  # noqa: E402
from database.config import SessionLocal  # noqa: E402
from identity.services import teams as team_service  # noqa: E402
from models import ROLE_MANAGER, Person, Team  # noqa: E402

SCHEMA = """
CREATE TABLE demo_marker (note TEXT);
CREATE TABLE channels (id INTEGER PRIMARY KEY, slack_channel_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL);
CREATE TABLE persons (id INTEGER PRIMARY KEY, display_name TEXT NOT NULL, slack_user_id TEXT UNIQUE, email TEXT);
CREATE TABLE standups (id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, standup_date DATE NOT NULL, UNIQUE (channel_id, standup_date));
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY, standup_id INTEGER NOT NULL, person_id INTEGER NOT NULL, last_week TEXT, this_week TEXT,
    blockers TEXT, combined TEXT, raw_content TEXT NOT NULL, is_late_reply BOOLEAN, source TEXT, created_at TEXT,
    UNIQUE (standup_id, person_id)
);
"""

# (last week, this week, blockers) for this week's standup, then for last week's. Invented engineering work. Index by
# the person's place on the team (manager first); with more people than entries they repeat.
THIS_WEEK = [
    (
        "- Closed the review of the bracket assembly BOM\n- Sent the revised bracket drawing to purchasing",
        "- Finish the BOM sign-off before Friday's design gate\n- Review the pilot build test plan with the validation team by Wednesday\n- Start the weld jig design for the rear axle",
        "- Waiting on the supplier's confirmation for the bracket samples",
    ),
    (
        "- Completed the first thermal run of the enclosure",
        "- Complete the thermal analysis of the enclosure and share the hot-spot summary\n- Update the DFMEA with the failure modes found in testing\n- Book the test rig for next week once the dates are confirmed",
        "",
    ),
    (
        # The long, messy one: weekday deadlines, a blocker, a handover, a carry-over, a leave line, routine noise, and two
        # items that repeat tasks already on the board, to see how a busy person's tab looks.
        "- Calibrated the load cell\n- Reviewed the fixture drawings\n- Fixed the tolerance stack-up on the housing\n- Supplier visit for the connector samples",
        "- Release the revised wiring harness drawing by Wednesday\n"
        "- Check connector stock with stores and report any shortfall\n"
        "- Close out the supplier corrective action report by Thursday\n"
        "- Prepare the vibration test summary slide for Friday's review\n"
        "- Hand over the fixture drawings to Aarav before my leave on 20 Nov\n"
        "- Finish the pilot build checklist, carried over from last week\n"
        "- Book the test rig for the week of 16 Nov\n"
        "- Routine fixture maintenance\n"
        "- Reply to the supplier emails\n"
        "- On leave from 20 Nov to 27 Nov",
        "- Pilot samples are stuck at customs, I need a customs clearance contact\n"
        "- Waiting on Aarav's thermal results before I can finalise the enclosure drawing",
    ),
]
LAST_WEEK = [
    ("- Prepared the bracket BOM", "- Draft the pilot build test plan\n- Order sample connectors from the supplier", ""),
    ("- Set up the thermal model", "- Run the first thermal analysis of the enclosure", ""),
    ("- Updated the harness routing", "- Calibrate the load cell\n- Review the fixture drawings", ""),
]
LATE_REPLY_INDEX = 1  # this person posts on the Wednesday, after the window closed


def build(path: Path, channel_id: str, channel_name: str, people: list[Person]) -> None:
    if path.exists():
        with sqlite3.connect(path) as old:
            try:
                old.execute("SELECT 1 FROM demo_marker").fetchone()
            except sqlite3.DatabaseError:
                sys.exit(f"{path} exists and was not made by this script, so it is left alone. Choose another --path.")
        path.unlink()

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    now = datetime.now(timezone.utc)

    def posted(day: date, days_after: int = 0) -> str:
        moment = min(datetime.combine(day + timedelta(days=days_after), time(4, 0), timezone.utc), now - timedelta(hours=1))
        return moment.strftime("%Y-%m-%d %H:%M:%S")  # the standup app stores UTC without a zone

    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO demo_marker VALUES ('made by seed/demo_standup_db.py')")
    con.execute("INSERT INTO channels VALUES (1, ?, ?)", (channel_id, channel_name))
    for week_id, day in ((1, monday - timedelta(days=7)), (2, monday)):
        con.execute("INSERT INTO standups VALUES (?, 1, ?)", (week_id, day.isoformat()))
    sub_id = 0
    for i, person in enumerate(people, start=1):
        con.execute("INSERT INTO persons VALUES (?, ?, ?, ?)", (i, person.name, person.slack_user_id, person.email))
        for week_id, day, entries in ((1, monday - timedelta(days=7), LAST_WEEK), (2, monday, THIS_WEEK)):
            last, this, blockers = entries[(i - 1) % len(entries)]
            late = week_id == 2 and (i - 1) == LATE_REPLY_INDEX
            raw = f"Last week:\n{last}\n\nThis week:\n{this}\n\nBlockers:\n{blockers}"
            sub_id += 1
            con.execute(
                "INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, 'slackbot_modal', ?)",
                (sub_id, week_id, i, last, this, blockers, raw, int(late), posted(day, 2 if late else 0)),
            )
    con.commit()
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--team", default="NPI", help="the team's name (default NPI, Manager 1's team in the demo world)")
    parser.add_argument("--path", default=str(ROOT / "seed" / "demo-standup.db"))
    args = parser.parse_args()
    if not settings.dev_auth:
        sys.exit("This is for development only: DEV_AUTH is off.")

    with SessionLocal() as db:
        team = db.scalar(select(Team).where(func.lower(Team.name) == args.team.lower()))
        if team is None:
            sys.exit(f"No team called {args.team}. Run `make db-demo` first, or pass --team.")
        people = list(db.scalars(select(Person).where(Person.team_id == team.id).order_by((Person.role == ROLE_MANAGER).desc(), Person.name)))
        if not people:
            sys.exit(f"{team.name} has no people yet.")
        channel_id = team.standup_channel_id or f"C0DEMO{team.name.upper().replace(' ', '')}"
        if not team.standup_channel_id:
            admin = db.scalar(select(Person).where(Person.is_admin.is_(True), Person.active.is_(True)).order_by(Person.created_at))
            if admin is None:
                sys.exit("No admin in the database to give the team a standup channel.")
            team_service.set_standup_channel(db, admin, team.id, channel_id, "Demo standup data")
            print(f"Gave {team.name} the standup channel {channel_id}.")
        path = Path(args.path).resolve()
        build(path, channel_id, f"standup-{team.name.lower().replace(' ', '-')}-demo", people)
        print(f"Wrote {path} for {len(people)} people on {team.name}: {', '.join(p.name for p in people)}.")
        print(f"\nPut this in .env (then restart the API), together with the LLM settings:\n  STANDUP_DB_URL=sqlite:///{path}")


if __name__ == "__main__":
    main()
