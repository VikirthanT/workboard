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
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import states
from core.config import settings
from core.exceptions import AppError
from models import Person
from security.authorization import can_login

log = logging.getLogger("workboard.auth")

# Google's public signing keys. Fetched on first use, then cached; a key Google rotates in is picked up after an hour.
_google_keys = jwt.PyJWKClient(states.GOOGLE_CERTS_URL, cache_keys=True, lifespan=3600, timeout=10)


def authorize_url(state: str, nonce: str) -> str:
    """Where to send the browser first. `hd` and `select_account` only steer Google's chooser towards the company
    account; the real domain check is `require_company_domain` below, because a hint is not a guarantee."""
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


def verify_signature(id_token: str) -> None:
    """Prove the ID token was signed by Google: RS256 only, against Google's published keys (fetched over TLS and
    cached for an hour), for our client id, from Google's issuer, and not expired. Fails closed: if the keys cannot
    be fetched nobody signs in. (The token also arrives straight from Google's token endpoint, which OpenID Connect
    Core 3.1.3.7 accepts on its own; this makes the signature a second, independent proof.)"""
    try:
        key = _google_keys.get_signing_key_from_jwt(id_token).key
        jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],  # a fixed list: a token cannot choose "none" or a shared-secret algorithm
            audience=settings.google_client_id,
            issuer=list(states.GOOGLE_ISSUERS),
            leeway=10,  # seconds of clock difference between us and Google
            options={"require": ["exp", "iss", "aud"]},
        )
    except (jwt.PyJWTError, ValueError) as problem:
        log.warning("Google ID token signature refused: %s", type(problem).__name__)  # never the token itself
        raise AppError(states.ERR_PROFILE, "Google sent an identity we cannot verify.", 400)


def verified_email(id_token: str, nonce: str, *, now: float | None = None) -> str:
    """The verified, lower-cased email in the ID token, or an AppError. Any domain: see `require_company_domain`.

    First the signature (`verify_signature`), then what the signature cannot say: that this is the token for *this*
    sign-in (the nonce) and that Google verified the email address.
    """
    verify_signature(id_token)
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
    return claims["email"].strip().lower()


def require_company_domain(email: str) -> None:
    if not email.endswith("@" + settings.allowed_email_domain):
        raise AppError(states.ERR_DOMAIN, f"Only @{settings.allowed_email_domain} accounts can sign in.", 403)


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
