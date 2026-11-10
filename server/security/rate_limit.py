"""Rate limits per login: each signed-in person, and each email trying to sign in, gets a budget of calls per window.

Keyed on who is calling, not on where from, so it works without knowing the real client address behind the proxies
(nginx adds a separate per-address limit for the endpoints that have no login yet). The numbers are far above normal
use (a manager moving cards makes a few requests a minute) and exist to stop a stuck script or a stolen session
from hammering the API.

shortcut: the counters live in this process's memory, and the API runs two worker processes, so a person's real
ceiling is up to twice the number below, and a restart clears them. Move them to the database or Redis if the limits
ever have to be exact.
"""
import threading
import time
from collections import deque

from core.exceptions import AppError

API_PER_MINUTE = 300  # every request by one signed-in person
IMPORT_PER_MINUTE = 6  # the bulk upload: it parses a spreadsheet, so it is the costly call
LOGIN_ATTEMPTS = 10  # Google sign-ins for one email in LOGIN_WINDOW_SECONDS, successful or refused
LOGIN_WINDOW_SECONDS = 600

_MAX_KEYS = 10_000  # when the table grows past this, keys idle for an hour are dropped
_IDLE_SECONDS = 3600

_lock = threading.Lock()
_calls: dict[tuple, deque[float]] = {}


def check(key: tuple, limit: int, window_seconds: float, *, now: float | None = None) -> None:
    """Count one call for `key`. Raises a 429 (with Retry-After) when it already made `limit` calls in the window."""
    now = time.monotonic() if now is None else now
    with _lock:
        calls = _calls.setdefault(key, deque())
        while calls and calls[0] <= now - window_seconds:
            calls.popleft()
        if len(calls) >= limit:
            wait = max(1, int(calls[0] + window_seconds - now) + 1)
            raise AppError(
                "rate_limited", "Too many requests. Wait a moment and try again.", 429, headers={"Retry-After": str(wait)}
            )
        calls.append(now)
        if len(_calls) > _MAX_KEYS:
            for stale in [k for k, c in _calls.items() if not c or c[-1] <= now - _IDLE_SECONDS]:
                del _calls[stale]


def reset() -> None:
    """Forget every count (the tests start each test clean)."""
    with _lock:
        _calls.clear()
