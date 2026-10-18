"""Signed, expiring tokens, with only the standard library.

A token is `base64url(payload) + "." + base64url(HMAC-SHA256(payload, SECRET_KEY))`. The payload carries what the
token is *for* (`kind`: "session" or "state") and when it ends (`exp`), so a token made for one purpose cannot be
passed off as the other, and an old one stops working by itself. Nothing is stored on the server for a token; if
SECRET_KEY changes, every token stops being valid, which is the way to sign everyone out at once.
"""
import base64
import hashlib
import hmac
import json
import time

from core.config import settings
from core.exceptions import AppError


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(payload_b64: str) -> str:
    return _b64(hmac.new(settings.secret_key.encode(), payload_b64.encode(), hashlib.sha256).digest())


def sign(kind: str, data: dict, ttl_seconds: int, *, now: float | None = None) -> str:
    """A token carrying `data`, good for `ttl_seconds`. Refuses to sign if SECRET_KEY is not set."""
    if len(settings.secret_key) < 32:
        raise AppError("auth_not_configured", "Sign-in is not set up: SECRET_KEY is missing or too short.", 501)
    payload = {**data, "kind": kind, "exp": int((now if now is not None else time.time()) + ttl_seconds)}
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_mac(payload_b64)}"


def verify(token: str, kind: str, *, now: float | None = None) -> dict | None:
    """The token's data, or None for any problem at all (malformed, wrong signature, wrong kind, expired).
    The caller never has to tell the problems apart: all of them mean "not signed in"."""
    if len(settings.secret_key) < 32 or token.count(".") != 1:
        return None
    payload_b64, mac = token.split(".")
    if not hmac.compare_digest(mac, _mac(payload_b64)):
        return None
    try:
        payload = json.loads(_unb64(payload_b64))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("kind") != kind:
        return None
    if int(payload.get("exp", 0)) <= (now if now is not None else time.time()):
        return None
    return payload
