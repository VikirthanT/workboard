"""Write audit entries for sign-ins (commands: add the row and commit once)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from auth import states
from identity import states as identity_states
from identity.services import audit
from models import AccessAuditLog, Person


def record_login(db: Session, person: Person) -> None:
    """Only the person is stored, as the actor: no team, no reason. The admin's audit log then shows who signed in and when."""
    audit.record(db, person, identity_states.AUTH_LOGIN)
    db.commit()


def record_refused_login(db: Session, email: str, code: str) -> None:
    """A refused sign-in by someone Google has verified: the reason is the error code, and the actor is the person when
    the directory knows the email (the email is kept in `details` either way). The same email and reason is written
    once per `REFUSED_LOGIN_QUIET_SECONDS`, so retrying cannot fill a log that can never be trimmed."""
    since = datetime.now(timezone.utc) - timedelta(seconds=states.REFUSED_LOGIN_QUIET_SECONDS)
    repeated = db.scalar(
        select(
            exists().where(
                AccessAuditLog.action == identity_states.AUTH_LOGIN_FAILED,
                AccessAuditLog.reason == code,
                AccessAuditLog.details["email"].as_string() == email,
                AccessAuditLog.created_at > since,
            )
        )
    )
    if repeated:
        return
    person = db.scalar(select(Person).where(Person.email == email))
    db.add(
        AccessAuditLog(
            actor_id=person.id if person else None,
            action=identity_states.AUTH_LOGIN_FAILED,
            reason=code,
            details={"email": email},
        )
    )
    db.commit()
