"""One-time login codes: the short-lived, single-use code Google sign-in puts in `/login?code=...`.

The browser trades it once for a session token, so the token itself never appears in an address, the history or a
log. Only a hash of the code is stored. `issue` is a command (it writes, commits once, returns nothing; the caller
makes the code, as with every create). `consume` is the one place a command also has to hand something back: it
marks the code used and returns who it was issued to, in a single database statement, so two requests with the
same code can never both succeed.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from auth.states import LOGIN_CODE_TTL_SECONDS
from models import LoginCode


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def issue(db: Session, person_id: uuid.UUID, code: str, *, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    db.execute(delete(LoginCode).where(LoginCode.expires_at < now - timedelta(hours=1)))  # tidy up old ones
    db.add(LoginCode(code_hash=_hash(code), person_id=person_id, expires_at=now + timedelta(seconds=LOGIN_CODE_TTL_SECONDS)))
    db.commit()


def consume(db: Session, code: str, *, now: datetime | None = None) -> uuid.UUID | None:
    """The person the code was issued to, and the code is now spent. None if it is unknown, expired or already used."""
    now = now or datetime.now(timezone.utc)
    person_id = db.execute(
        update(LoginCode)
        .where(LoginCode.code_hash == _hash(code), LoginCode.used_at.is_(None), LoginCode.expires_at > now)
        .values(used_at=now)
        .returning(LoginCode.person_id)
    ).scalar_one_or_none()
    db.commit()
    return person_id
