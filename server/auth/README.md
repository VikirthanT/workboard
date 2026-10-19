# auth

Google sign-in: how a person proves who they are. Everything is under `/api`. The three endpoints are called in order:
the button goes to step 1, Google sends the browser to step 2, the login page calls step 3.

```
 browser            our API                         Google
    │  GET /auth/google  │                              │
    │───────────────────►│ state + nonce in a cookie    │
    │◄── 302 to Google ──│                              │
    │───────────── person signs in at Google ──────────►│
    │◄──────────── 302 to /api/auth/google/callback ────│  (code, state)
    │  GET /callback     │                              │
    │───────────────────►│── trade the code (+ secret) ─►│
    │                    │◄── ID token: who they are ────│
    │                    │ is it the right token? a company email? an active manager or admin?
    │◄─ 302 /login?code=<one-time code> (or /login?error=<reason>)
    │  GET /exchange?code=
    │───────────────────►│ code is single-use, 60 seconds
    │◄── {token, email, name}   then every call sends  Authorization: Bearer <token>
```

## Endpoints

| Method and path | Who | File | What it does |
| --- | --- | --- | --- |
| `GET /api/auth/google` | anyone | `routers/google.py` | Sends the browser to Google with a random `state` and `nonce`, remembered in a short-lived, HttpOnly, signed cookie. Without every Google setting it goes to `/login?error=oauth_not_configured`. |
| `GET /api/auth/google/callback` | Google, via the browser | `routers/google.py` | Checks the `state` against the cookie, trades Google's code for the ID token, checks the token, and checks the person may sign in. On success it issues a one-time code and redirects to `/login?code=...`; on any failure to `/login?error=<code>`. It never signs anyone in by itself. |
| `GET /api/auth/google/exchange?code=` | anyone with a code | `routers/google.py` | Trades the one-time code for `{token, email, name}`. The code works once, for 60 seconds. `Cache-Control: no-store`. |

A signed-in call then sends `Authorization: Bearer <token>`; `security/authentication.py` (`get_current_person`) verifies it.
The development header (`X-Dev-User-Email`) still works, only while `DEV_AUTH` is on.

## What is checked, and the error each failure gives

Redirect errors (`/login?error=...`; the login page has a message for each, listed in `auth/states.py`):

| Code | Meaning |
| --- | --- |
| `oauth_not_configured` | A Google setting or `SECRET_KEY` is missing (or the key is under 32 characters). |
| `oauth_denied` | The person pressed cancel at Google. |
| `invalid_state` | The callback did not come from a sign-in started here: missing, forged, wrong or expired cookie, or no code. |
| `token_exchange_failed` | Google would not give an identity for the code (also the exchange step's error for a code that is unknown, used or expired). |
| `userinfo_failed` | The token is not valid for us: wrong issuer or audience, expired, wrong `nonce`, email not verified, or unreadable. |
| `domain_not_allowed` | The verified email is not on `ALLOWED_EMAIL_DOMAIN`. Matched as a whole suffix (`@atimotors.com`), so `x@atimotors.com.evil.com` does not pass. |
| `not_onboarded` | A real company account, but not an active manager or admin. |

API errors from a token: 401 `not_authenticated` (missing, malformed, altered, expired or with an unusable expiry, wrong kind of token, or the person
is gone), 403 `not_onboarded` (the person lost their role since the token was made: a token never outlives the role).

## Settings (in `.env`, see `.env.example`)

`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SECRET_KEY` (at least 32 characters: signs tokens and the
state cookie), `TOKEN_TTL_SECONDS` (session length, default 28800 = 8 hours). Changing `SECRET_KEY` signs everyone out.

## Folder map

```
server/auth/
├── routers/
│   ├── __init__.py        assembles the one `router`
│   └── google.py          the three endpoints
├── services/
│   ├── google.py          authorize_url, exchange_code (talks to Google), read_identity (checks the token), person_for_email
│   ├── tokens.py          sign / verify: signed, expiring tokens with the standard library only
│   └── login_codes.py     issue / consume: one-time codes, stored as hashes (table `login_codes`, migration 0003)
├── schemas.py             SessionResponse
└── states.py              cookie name, lifetimes, Google addresses, the error codes
```

Shared code used here: `server/security/authentication.py` (accepts the token), `server/security/authorization.py`
(`can_login`), `server/models/login_codes.py`, `server/core/config.py` (the settings).

## Design notes

- **Why two steps (callback, then exchange)?** The callback is a browser navigation, so its result has to travel in the
  address. Putting the real session token there would leave it in the history and in logs; a 60-second, single-use code is harmless.
- **No signature check on Google's ID token** (deliberately): it arrives directly from Google's token endpoint over TLS in answer to a
  request carrying our client secret, which OpenID Connect (Core 3.1.3.7) accepts instead. Every claim is still checked.
- **No new packages**: tokens are HMAC-SHA256 over a JSON payload; HTTP to Google uses `httpx`, already installed.
- **Nothing is stored for a session token**; sign everyone out by changing `SECRET_KEY`. Only the one-time codes are in the database.

## Not built yet

- Server-side sign-out (the browser just forgets the token; it expires by itself).
- Trying it against real Google needs the OAuth client and the settings; see `docs/DEPLOYMENT.md`.

Tests: `server/tests/test_google_auth.py` (70 tests; Google's answers are faked).
