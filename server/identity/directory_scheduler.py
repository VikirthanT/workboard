"""Refreshes the people directory from the Slack workspace, once or on a schedule.

    python -m identity.directory_scheduler [--once] [--allow-large-removal]    from server/
    make db-sync-people        (development)        make prod-sync-people        (the running production stack)

With `--once` it runs now and exits: that is how the first load happens, and how a run is repeated by hand. Without it, it is a
long-lived process that runs at the times in DIRECTORY_SYNC_SCHEDULE (India time, for example `sun 22:00`) and idles when
that is empty; the production stack runs it as the `directory-sync` service (docker-compose.yml). It needs SLACK_BOT_TOKEN
(`users:read` and `users:read.email`); without it a run says so and does nothing.

The rules (who is listed, who is deactivated, the removal limit) are in identity/services/directory_sync.py, and every run is
written to the audit log. A run that fails (Slack unreachable, the removal limit) is logged and the schedule carries on.
"""
import argparse
import logging
import sys
import threading
import time as clock
from datetime import datetime

from core.config import get_settings
from core.exceptions import AppError
from core.schedule import next_run, parse_schedule
from database.config import SessionLocal
from identity.services import directory_sync
from slack import client as slack

logger = logging.getLogger(__name__)


def run_once(*, allow_large_removal: bool = False, reason: str = "Weekly Slack sync") -> bool:
    """One run. True if the directory was synced; False if Slack is not set up or the run failed (the cause is logged)."""
    settings = get_settings()
    if not settings.slack_configured:
        print("Directory sync skipped: SLACK_BOT_TOKEN is not set (see docs/SLACK_SETUP.md).")
        return False
    try:
        raw = slack.list_users(settings.slack_bot_token)
        with SessionLocal() as db:
            directory_sync.sync_directory(db, raw, allow_large_removal=allow_large_removal, reason=reason)
            details = (directory_sync.last_run(db).details) or {}
    except slack.SlackError as err:
        logger.error("Directory sync failed: Slack could not be read. %s", err)
        return False
    except AppError as err:
        logger.error("Directory sync refused: %s", err.message)
        return False
    print(
        f"directory sync: {details['people']} people in Slack, {details['added']} added, {details['reactivated']} back, "
        f"{details['deactivated']} deactivated ({details['deactivated_on_a_team']} of them on a team), "
        f"{len(details['new_admins'])} new admin(s), {details['skipped']} skipped"
    )
    for email in details["missing_admins"]:
        print(f"  warning: bootstrap admin {email} is not in Slack, so was not made admin")
    for note in details["notes"]:
        print(f"  skipped {note}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--once", action="store_true", help="run now and exit")
    parser.add_argument("--allow-large-removal", action="store_true", help="allow a run that deactivates many people (with --once)")
    args = parser.parse_args(argv)

    if args.once:
        ran = run_once(allow_large_removal=args.allow_large_removal, reason="Run by hand")
        return 0 if ran or not get_settings().slack_configured else 1

    schedule = get_settings().directory_sync_schedule
    try:
        slots = parse_schedule(schedule)
    except ValueError as err:
        print(f"Directory sync not started: DIRECTORY_SYNC_SCHEDULE is wrong. {err}")
        slots = []
    if not slots:
        print('Directory sync idle: set DIRECTORY_SYNC_SCHEDULE in .env, for example "sun 22:00" (see .env.example).')
        threading.Event().wait()
        return 0
    print(f"Directory sync running: {schedule}")
    while True:
        due = next_run(datetime.now(), slots)
        print(f"Next directory sync: {due:%a %d %b %H:%M}")
        while datetime.now() < due:
            clock.sleep(min(30.0, max(1.0, (due - datetime.now()).total_seconds())))  # short sleeps, so a changed clock is noticed
        run_once()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
