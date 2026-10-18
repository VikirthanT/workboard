"""Google sign-in: three endpoints, called in this order.

  1. GET /auth/google            the "Continue with Google" button goes here; we send the browser to Google.
  2. GET /auth/google/callback   Google sends the browser back here; we decide whether to let the person in.
  3. GET /auth/google/exchange   the login page trades the one-time code from step 2 for a session token.

Steps 1 and 2 are navigations (the browser is moved from page to page), so they answer with redirects, never JSON;
a failure goes back to the login page as `/login?error=<code>`. Redirects are relative on purpose: the callback is
reached through the frontend's own address (the Vite proxy in development, nginx in production), so `/login` is
the login page on the same site. Step 3 is an ordinary API call and answers JSON.
"""
import hmac
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth import schemas, states
from auth.services import google, login_codes, tokens
from core.config import settings
from core.exceptions import AppError
from database.config import get_db
from models import Person
from security.authorization import can_login

router = APIRouter(prefix="/auth/google", tags=["auth"])
log = logging.getLogger("workboard.auth")

COOKIE_PATH = "/api/auth/google"


def _back_to_login(error: str) -> RedirectResponse:
    """Send the browser to the login page with the reason; the page shows a message for each code."""
    response = RedirectResponse(f"/login?error={error}", status_code=302)
    response.delete_cookie(states.STATE_COOKIE, path=COOKIE_PATH)
    return response


@router.get("", include_in_schema=False)
def start() -> RedirectResponse:
    """Begin sign-in: remember this attempt in a signed cookie, then send the browser to Google.

    The cookie holds a random `state` (also sent to Google and checked on the way back, so a callback we did not
    start is refused) and a random `nonce` (checked inside Google's answer, so an old answer cannot be replayed).
    It is HttpOnly, so scripts on the page cannot read it, and lives ten minutes.
    """
    if not settings.google_configured:
        return _back_to_login(states.ERR_NOT_CONFIGURED)
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    response = RedirectResponse(google.authorize_url(state, nonce), status_code=302)
    response.set_cookie(
        states.STATE_COOKIE,
        tokens.sign("state", {"state": state, "nonce": nonce}, states.STATE_TTL_SECONDS),
        max_age=states.STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",  # sent when Google redirects the browser back, not on other sites' requests
        secure=settings.google_redirect_uri.startswith("https://"),
        path=COOKIE_PATH,
    )
    return response


@router.get("/callback", include_in_schema=False)
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Finish sign-in. On success the browser goes to `/login?code=<one-time code>`; on any failure to
    `/login?error=<code>` (the codes are in `auth/states.py`). Nobody is ever signed in by this step alone: it only
    issues a code, which `exchange` turns into a session."""
    if not settings.google_configured:
        return _back_to_login(states.ERR_NOT_CONFIGURED)
    if error:  # Google reports the person cancelled (access_denied) or something went wrong on its side
        return _back_to_login(states.ERR_DENIED)
    saved = tokens.verify(request.cookies.get(states.STATE_COOKIE, ""), "state")
    if not (saved and code and state and hmac.compare_digest(saved["state"], state)):
        return _back_to_login(states.ERR_STATE)
    try:
        id_token = google.exchange_code(code)
        email = google.read_identity(id_token, saved["nonce"])
        person = google.person_for_email(db, email)
    except AppError as refused:
        log.warning("Google sign-in refused: %s (%s)", refused.code, refused.message)
        return _back_to_login(refused.code)
    one_time_code = secrets.token_urlsafe(32)
    login_codes.issue(db, person.id, one_time_code)
    response = RedirectResponse(f"/login?code={one_time_code}", status_code=302)
    response.delete_cookie(states.STATE_COOKIE, path=COOKIE_PATH)
    return response


@router.get("/exchange", response_model=schemas.SessionResponse)
def exchange(code: str, response: Response, db: Session = Depends(get_db)):
    """Trade the one-time code for a session token. The code works once, for sixty seconds.

    The token is signed and expires after `TOKEN_TTL_SECONDS`; the browser sends it as `Authorization: Bearer`.
    The person is checked again here (they may have lost their role in the last minute).
    Errors: 400 `token_exchange_failed` for a code that is unknown, used or expired; 403 `not_onboarded` if they
    can no longer sign in.
    """
    response.headers["Cache-Control"] = "no-store"
    person_id = login_codes.consume(db, code)
    person = db.get(Person, uuid.UUID(str(person_id))) if person_id else None
    if person is None:
        log.warning("One-time login code refused: unknown, already used or expired")
        raise AppError(states.ERR_EXCHANGE, "That sign-in link has expired or was already used. Sign in again.", 400)
    if not can_login(person):
        raise AppError(states.ERR_NOT_ONBOARDED, "This account is not set up as a manager or admin.", 403)
    token = tokens.sign("session", {"sub": str(person.id)}, settings.token_ttl_seconds)
    return schemas.SessionResponse(token=token, email=person.email, name=person.name)
