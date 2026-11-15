"""Keeps the people directory in step with the Slack workspace. Slack is the source of truth for who exists.

`sync_directory` is a command: it checks, writes, and commits once. `members_from_slack` and `last_run` are queries.

What a run does with the workspace's people:
  - people in it are added, or have their name and email refreshed and are marked active again;
  - people already in the database but missing from it have left, and are marked inactive (never deleted: the audit
    history and tasks still point at them). Admins, and the development demo accounts, are never deactivated;
  - role, team and admin flag of existing people are never overwritten;
  - the people in BOOTSTRAP_ADMIN_EMAILS are made admin if they are not (this is how the first admin gets in);
  - bots, Slackbot, deactivated accounts, guests, people with no email and people outside the company domain are not listed.
A run that would deactivate more than the larger of 20 people or 10% of the directory is refused unless forced, and a
Slack list with nobody usable in it changes nothing: a truncated or wrong answer would otherwise deactivate everyone.
Each run writes one `directory.sync` row to the append-only audit log, with the counts.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import AppError
from identity import states
from models import AccessAuditLog, Person
from security.authorization import require_admin
from slack import client as slack

MIN_REMOVALS_ALLOWED = 20
MAX_REMOVAL_SHARE = 0.10
NOTES_KEPT = 20  # skipped-person notes kept in the audit entry


@dataclass(frozen=True)
class Member:
    slack_user_id: str
    email: str
    name: str


def _is_person(item: dict) -> bool:
    """A full member of the workspace: not a bot, Slackbot, a deactivated account or a guest."""
    profile = item.get("profile") or {}
    return not (
        item.get("deleted") or item.get("is_bot") or profile.get("bot_id") or item.get("id") == "USLACKBOT"
        or item.get("is_restricted") or item.get("is_ultra_restricted")
    )


def people_in_slack(raw: list[dict]) -> set[str]:
    """The Slack ids of everyone who is still a person in the workspace, listed or not. Someone whose entry has no usable
    email today is still here, so is not treated as having left."""
    return {str(item.get("id") or "").strip() for item in raw if _is_person(item)} - {""}


def members_from_slack(raw: list[dict], domain: str) -> tuple[list[Member], list[str]]:
    """The people to list, from Slack's `users.list` answer, plus a note for each person skipped for a reason worth reading
    (no name or email, another domain, a duplicate). Bots, deactivated accounts and guests are left out without a note."""
    suffix = "@" + domain
    members: list[Member] = []
    notes: list[str] = []
    seen_emails: set[str] = set()
    seen_ids: set[str] = set()
    for item in raw:
        if not _is_person(item):
            continue
        slack_id = str(item.get("id") or "").strip()
        profile = item.get("profile") or {}
        email = (profile.get("email") or "").strip().lower()
        name = (profile.get("display_name") or profile.get("real_name") or item.get("real_name") or item.get("name") or "").strip()
        if not (slack_id and email and name):
            notes.append(f"{slack_id or '?'}: missing a name, email or Slack id")
        elif not email.endswith(suffix):
            notes.append(f"{slack_id}: email is not {suffix}")
        elif email in seen_emails or slack_id in seen_ids:
            notes.append(f"{slack_id}: duplicate email or Slack id")
        else:
            seen_emails.add(email)
            seen_ids.add(slack_id)
            members.append(Member(slack_id, email, name))
    return members, notes


def sync_from_slack(db: Session, actor: Person) -> None:
    """An admin's "Sync people from Slack": the same run as the weekly one, started by a person and recorded under their
    name. Reads the workspace, then merges it (see `sync_directory`). The removal limit still applies; forcing it is done
    from the command line, not from the page."""
    require_admin(actor)
    settings = get_settings()
    if not settings.slack_configured:
        raise AppError("slack_not_configured", "Slack is not set up on this server, so the people cannot be read from it.", 501)
    try:
        raw = slack.list_users(settings.slack_bot_token)
    except slack.SlackError as err:
        raise AppError("slack_failed", f"Slack could not be read. {err}", 502) from err
    sync_directory(db, raw, reason="Run from the Teams portal", actor=actor)


def last_run(db: Session) -> AccessAuditLog | None:
    """The newest `directory.sync` entry of the audit log, or None if the directory was never synced."""
    return db.scalar(
        select(AccessAuditLog).where(AccessAuditLog.action == states.DIRECTORY_SYNC).order_by(AccessAuditLog.created_at.desc()).limit(1)
    )


def sync_directory(
    db: Session,
    raw_members: list[dict],
    *,
    allow_large_removal: bool = False,
    reason: str = "Weekly Slack sync",
    actor: Person | None = None,
) -> None:
    """`actor` is the admin who started the run from the Teams portal; the server's own runs have none."""
    settings = get_settings()
    members, notes = members_from_slack(raw_members, settings.allowed_email_domain)
    if not members:
        raise AppError("directory_empty", "Slack returned nobody who can be listed, so nothing was changed.", 502)

    people = list(db.scalars(select(Person)))
    by_slack = {p.slack_user_id: p for p in people}
    by_email = {p.email: p for p in people}

    usable: list[Member] = []
    for m in members:
        owner = by_email.get(m.email)
        if owner is not None and owner.slack_user_id != m.slack_user_id:
            notes.append(f"{m.slack_user_id}: that email already belongs to another person")  # their row is left as it is
        else:
            usable.append(m)

    present = people_in_slack(raw_members)  # a person skipped for a data problem is still in Slack, so has not left
    added = [m for m in usable if m.slack_user_id not in by_slack]
    reactivated = [m for m in usable if m.slack_user_id in by_slack and not by_slack[m.slack_user_id].active]
    active = [p for p in people if p.active]
    leaving = [
        p for p in active
        if p.slack_user_id not in present and not p.is_admin and not p.slack_user_id.startswith(states.DEMO_SLACK_PREFIX)
    ]
    allowed = max(MIN_REMOVALS_ALLOWED, int(len(active) * MAX_REMOVAL_SHARE))
    if len(leaving) > allowed and not allow_large_removal:
        raise AppError(
            "directory_removal_too_large",
            f"This would deactivate {len(leaving)} of {len(active)} people (limit {allowed}). If that is right, run it again forced.",
            409,
        )

    statement = insert(Person).values([{"slack_user_id": m.slack_user_id, "email": m.email, "name": m.name} for m in usable])
    db.execute(statement.on_conflict_do_update(
        index_elements=["slack_user_id"],
        set_={"name": statement.excluded.name, "email": statement.excluded.email, "active": True},
    ))
    db.expire_all()  # the insert above went around the loaded rows; read them again before changing any

    new_admins: list[str] = []
    missing_admins: list[str] = []
    for email in settings.admin_emails:
        person = db.scalar(select(Person).where(Person.email == email))
        if person is None:
            missing_admins.append(email)
        elif not person.is_admin:
            person.is_admin = True
            db.add(AccessAuditLog(action=states.ADMIN_GRANT, person_id=person.id, reason="Bootstrap admin from the Slack sync"))
            new_admins.append(email)

    for person in leaving:
        person.active = False

    db.add(AccessAuditLog(
        action=states.DIRECTORY_SYNC,
        actor_id=actor.id if actor else None,
        reason=reason,
        details={
            "slack_members": len(raw_members),
            "people": len(members),
            "added": len(added),
            "reactivated": len(reactivated),
            "deactivated": len(leaving),
            "deactivated_on_a_team": sum(1 for p in leaving if p.team_id is not None),
            "new_admins": new_admins,
            "missing_admins": missing_admins,
            "skipped": len(notes),
            "notes": notes[:NOTES_KEPT],
        },
    ))
    db.commit()
