"""Talking to Google, and deciding whether what Google says lets the person in.

The flow (OpenID Connect "authorization code"): we send the browser to Google with a random `state` and `nonce`;
Google signs the person in and sends the browser back with a one-time `code`; we trade that code (plus our client
secret) for an ID token that names the person; we check the token says what we need. The three functions here are
those three steps. Any failure is an AppError whose `code` is a `/login?error=` value from `auth/states.py`.
"""
import base64
import hmac
import json
import logging
import time
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import states
from core.config import settings
from core.exceptions import AppError
from models import Person
from security.authorization import can_login

log = logging.getLogger("workboard.auth")


def authorize_url(state: str, nonce: str) -> str:
    """Where to send the browser first. `hd` and `select_account` only steer Google's chooser towards the company
    account; the real domain check is `read_identity` below, because a hint is not a guarantee."""
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "hd": settings.allowed_email_domain,
            "prompt": "select_account",
        }
    )
    return f"{states.GOOGLE_AUTH_URL}?{query}"


def exchange_code(code: str) -> str:
    """Trade Google's one-time code for the ID token. Google only does this for our client id and secret."""
    try:
        response = httpx.post(
            states.GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        body = response.json()
        token = body.get("id_token") if response.status_code == 200 else None
        if token is None:
            # Google says why in plain words (invalid_client = wrong secret, redirect_uri_mismatch, invalid_grant = code
            # already used or expired). Neither field holds a secret, so it is safe, and very useful, to log.
            log.warning("Google refused the code: %s %s (%s)", response.status_code, body.get("error"), body.get("error_description"))
    except (httpx.HTTPError, ValueError) as problem:
        log.warning("Could not reach Google's token endpoint: %s", type(problem).__name__)
        token = None
    if not isinstance(token, str):
        raise AppError(states.ERR_EXCHANGE, "Google would not confirm the sign-in.", 400)
    return token


def read_identity(id_token: str, nonce: str, *, now: float | None = None) -> str:
    """The verified, lower-cased email in the ID token, or an AppError.

    The signature is not re-checked here on purpose: this token came straight from Google's token endpoint, over
    TLS, in answer to a request carrying our client secret, which OpenID Connect (Core 3.1.3.7) accepts in place
    of checking the signature. What we do check is that it is the right token: from Google, for our client, still
    valid, for this sign-in (the nonce), and about a verified email on the company domain.
    """
    claims = _claims(id_token)
    audience = claims.get("aud")
    valid = (
        claims.get("iss") in states.GOOGLE_ISSUERS
        and (audience == settings.google_client_id or (isinstance(audience, list) and settings.google_client_id in audience))
        and isinstance(claims.get("exp"), (int, float))
        and claims["exp"] > (now if now is not None else time.time())
        and isinstance(claims.get("nonce"), str)
        and hmac.compare_digest(claims["nonce"], nonce)
        and claims.get("email_verified") is True
        and isinstance(claims.get("email"), str)
    )
    if not valid:
        raise AppError(states.ERR_PROFILE, "Google sent an identity we cannot accept.", 400)
    email = claims["email"].strip().lower()
    if not email.endswith("@" + settings.allowed_email_domain):
        raise AppError(states.ERR_DOMAIN, f"Only @{settings.allowed_email_domain} accounts can sign in.", 403)
    return email


def person_for_email(db: Session, email: str) -> Person:
    """The person this email belongs to, if they may sign in at all: an active manager or admin."""
    person = db.scalar(select(Person).where(Person.email == email))
    if person is None or not can_login(person):
        raise AppError(states.ERR_NOT_ONBOARDED, "This account is not set up as a manager or admin.", 403)
    return person


def _claims(id_token: str) -> dict:
    """The JSON in the middle of the token (header.payload.signature)."""
    parts = id_token.split(".")
    try:
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (IndexError, ValueError):
        claims = None
    if not isinstance(claims, dict):
        raise AppError(states.ERR_PROFILE, "Google sent an identity we cannot read.", 400)
    return claims
