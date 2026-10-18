"""Load the people directory into Postgres and make the bootstrap admins.

    server/.venv/bin/python seed/load_db.py [path] [--allow-large-removal]     (or: make db-seed)

Needs the database up and migrated and BOOTSTRAP_ADMIN_EMAILS set (make db-seed loads both from .env).
Safe to run again.

The file is the whole current directory (the path argument, else PEOPLE_FILE from the environment; a folder means
<folder>/people.json). people.json is a list of {displayName, email, slackUserId}, made from the Slack user cache
by csv_to_people.py; refdocs/usersextract.json, a list of
{display_name, email, slack_user_id}, works too). Real people, gitignored. So:
  - people in it are added, or have their name and email refreshed and are marked active again;
  - people already in the database but missing from it have left, and are marked inactive
    (not deleted: audit history and, later, tasks still point at them). Admins are never deactivated;
  - role, team and admin flag of existing people are never overwritten.
Creates no teams: the admin creates those in the admin panel.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from core.config import settings  # noqa: E402
from database.config import SessionLocal  # noqa: E402
from identity import states  # noqa: E402
from models import AccessAuditLog, Person  # noqa: E402


# A truncated or wrong file would otherwise deactivate everyone, so a big removal needs an explicit flag.
MIN_REMOVALS_ALLOWED = 20
MAX_REMOVAL_SHARE = 0.10


def read_directory(path: Path) -> tuple[list[dict], list[str]]:
    """Valid rows for the people table, plus a note for every row that was skipped and why."""
    if not path.exists():
        sys.exit(f"{path} is missing. Pass the path of the directory extract as the first argument.")
    rows, skipped, seen_emails, seen_slack = [], [], set(), set()
    suffix = "@" + settings.allowed_email_domain
    for raw in json.loads(path.read_text(encoding="utf-8")):
        email = raw.get("email", "").strip().lower()
        slack_id = (raw.get("slack_user_id") or raw.get("slackUserId") or "").strip()  # extract or people.json
        name = (raw.get("display_name") or raw.get("displayName") or "").strip()
        if not (email and slack_id and name):
            skipped.append(f"{slack_id or '?'}: missing a name, email or Slack id")
        elif not email.endswith(suffix):
            skipped.append(f"{slack_id}: email is not {suffix}")
        elif email in seen_emails or slack_id in seen_slack:
            skipped.append(f"{slack_id}: duplicate email or Slack id")
        else:
            seen_emails.add(email)
            seen_slack.add(slack_id)
            rows.append({"slack_user_id": slack_id, "email": email, "name": name})
    return rows, skipped


def upsert_people(db: Session, rows: list[dict]) -> None:
    """Add new people; for people already there, refresh name and email and mark them active again."""
    statement = insert(Person).values(rows)
    db.execute(
        statement.on_conflict_do_update(
            index_elements=["slack_user_id"],
            set_={"name": statement.excluded.name, "email": statement.excluded.email, "active": True},
        )
    )


def deactivate_missing(db: Session, present_slack_ids: set[str], *, allow_large_removal: bool = False) -> list[Person]:
    """Mark active people who are not in the file as inactive. Returns the people deactivated."""
    active = list(db.scalars(select(Person).where(Person.active.is_(True))).unique())
    # The development demo accounts are not in the Slack file by design; they must not be deactivated by a load.
    leaving = [
        p for p in active
        if p.slack_user_id not in present_slack_ids and not p.is_admin and not p.slack_user_id.startswith(states.DEMO_SLACK_PREFIX)
    ]
    allowed = max(MIN_REMOVALS_ALLOWED, int(len(active) * MAX_REMOVAL_SHARE))
    if len(leaving) > allowed and not allow_large_removal:
        sys.exit(f"This file would deactivate {len(leaving)} of {len(active)} people (limit {allowed}). "
                 f"If that is right, run again with --allow-large-removal.")
    for person in leaving:
        person.active = False
    return leaving


def grant_bootstrap_admins(db: Session, emails: list[str]) -> list[str]:
    """Make each listed person an admin. Returns the emails that were newly granted."""
    granted = []
    for email in emails:
        person = db.scalar(select(Person).where(Person.email == email))
        if person is None:
            sys.exit(f"{email} is not in the people directory, so they cannot be made admin. "
                     f"Check the address, or add them to the directory file first.")
        if person.is_admin:
            continue
        person.is_admin = True
        db.add(AccessAuditLog(action=states.ADMIN_GRANT, person_id=person.id, reason="bootstrap admin from seed"))
        granted.append(email)
    return granted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("path", nargs="?", type=Path, default=os.environ.get("PEOPLE_FILE") or None)
    parser.add_argument("--allow-large-removal", action="store_true")
    args = parser.parse_args()

    path = args.path
    if path is None:
        sys.exit("No people file. Pass its path, or set PEOPLE_FILE (make db-seed does that from .env).")
    if path.is_dir():
        path = path / "people.json"  # PEOPLE_FILE may be a folder that holds people.json

    admin_emails = settings.admin_emails
    if not admin_emails:
        sys.exit("BOOTSTRAP_ADMIN_EMAILS is empty. Set it in .env, e.g. BOOTSTRAP_ADMIN_EMAILS=first.admin@your-domain.com")

    rows, skipped = read_directory(path)
    with SessionLocal() as db:
        upsert_people(db, rows)
        granted = grant_bootstrap_admins(db, admin_emails)
        left = deactivate_missing(db, {r["slack_user_id"] for r in rows}, allow_large_removal=args.allow_large_removal)
        db.commit()
        still_on_teams = sum(1 for p in left if p.team_id is not None)

    print(f"seed: {len(rows)} people in the file, {len(skipped)} skipped, {len(granted)} new admin(s), "
          f"{len(left)} deactivated ({still_on_teams} of them still on a team)")
    for note in skipped:
        print(f"  skipped {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
