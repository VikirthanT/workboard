"""Who is calling. Every protected endpoint asks `get_current_person`, which answers with a person or refuses.

Two ways in, tried in this order:
  1. `Authorization: Bearer <token>`: the session token Google sign-in hands out (`auth/`). This is the real way,
     and the only one in production.
  2. The `X-Dev-User-Email` header, only while DEV_AUTH=true (local development and tests).
With neither: 401 `not_authenticated` if sign-in is possible here, else 501 `auth_not_configured` (no DEV_AUTH and no
Google settings, so nobody could ever get in; the answer says so instead of a misleading 401).

Whichever way, the person must be an active manager or admin (`can_login`) *now*: a token does not outlive the role.
"""
import uuid

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.services import tokens
from core.config import settings
from core.exceptions import AppError
from database.config import get_db
from models import Person
from security.authorization import can_login

DEV_HEADER = "X-Dev-User-Email"


def _not_onboarded() -> AppError:
    return AppError("not_onboarded", "This account is not set up as a manager or admin.", 403)


def get_current_person(request: Request, db: Session = Depends(get_db)) -> Person:
    scheme, _, credential = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credential:
        return _person_from_token(db, credential.strip())
    if settings.dev_auth:
        return _person_from_dev_header(request, db)
    if settings.google_configured:
        raise AppError("not_authenticated", "Sign in first.", 401)
    raise AppError("auth_not_configured", "Sign-in is not set up yet.", 501)


def _person_from_token(db: Session, token: str) -> Person:
    claims = tokens.verify(token, "session")
    try:
        person = db.get(Person, uuid.UUID(claims["sub"])) if claims else None
    except (KeyError, ValueError):
        person = None
    if claims is None or person is None:
        raise AppError("not_authenticated", "Your session has ended. Sign in again.", 401)
    if not can_login(person):
        raise _not_onboarded()
    return person


def _person_from_dev_header(request: Request, db: Session) -> Person:
    email = request.headers.get(DEV_HEADER, "").strip().lower()
    if not email:
        raise AppError("not_authenticated", "Sign in first.", 401)
    if not email.endswith("@" + settings.allowed_email_domain):
        raise AppError("domain_not_allowed", f"Only @{settings.allowed_email_domain} accounts can sign in.", 403)
    person = db.scalar(select(Person).where(Person.email == email))
    if person is None or not can_login(person):
        raise _not_onboarded()
    return person
