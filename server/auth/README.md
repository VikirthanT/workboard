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

| `POST /api/auth/logout` | anyone signed in | `routers/session.py` | Signs the person out everywhere: adds one to their `session_version`, so every token already issued to them stops working at once (401). Returns 204. |

A signed-in call then sends `Authorization: Bearer <token>`; `security/authentication.py` (`get_current_person`) verifies it, checks the
token's `ver` against the person's `session_version`, and counts the call against that person's rate limit.
The development header (`X-Dev-User-Email`) still works, only while `DEV_AUTH` is on (nginx blanks it in production).

## What is checked, and the error each failure gives

Redirect errors (`/login?error=...`; the login page has a message for each, listed in `auth/states.py`):

| Code | Meaning |
| --- | --- |
| `oauth_not_configured` | A Google setting or `SECRET_KEY` is missing (or the key is under 32 characters). |
| `oauth_denied` | The person pressed cancel at Google. |
| `invalid_state` | The callback did not come from a sign-in started here: missing, forged, wrong or expired cookie, or no code. |
| `token_exchange_failed` | Google would not give an identity for the code (also the exchange step's error for a code that is unknown, used or expired). |
| `userinfo_failed` | The token is not valid for us: not signed by Google (or Google's keys could not be fetched), wrong issuer or audience, expired, wrong `nonce`, email not verified, or unreadable. |
| `too_many_attempts` | This email has tried to sign in more than 10 times in the last 10 minutes. |
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
│   ├── google.py          the three Google endpoints
│   └── session.py         POST /auth/logout
├── services/
│   ├── google.py          authorize_url, exchange_code (talks to Google), verify_signature, verified_email (checks the token), require_company_domain, person_for_email
│   ├── sessions.py        end_sessions: logout adds one to the person's session_version
│   ├── tokens.py          sign / verify: signed, expiring tokens with the standard library only
│   ├── login_codes.py     issue / consume: one-time codes, stored as hashes (table `login_codes`, migration 0003)
│   └── login_audit.py     record_login, record_refused_login: the sign-in entries in the audit log
├── schemas.py             SessionResponse
└── states.py              cookie name, lifetimes, Google addresses, the error codes
```

Shared code used here: `server/security/authentication.py` (accepts the token), `server/security/authorization.py`
(`can_login`), `server/models/login_codes.py`, `server/core/config.py` (the settings).

## Design notes

- **Why two steps (callback, then exchange)?** The callback is a browser navigation, so its result has to travel in the
  address. Putting the real session token there would leave it in the history and in logs; a 60-second, single-use code is harmless.
- **Google's ID token is checked for its signature** (`google.verify_signature`, PyJWT with `cryptography`): RS256 only, against Google's
  published keys (fetched over TLS, cached for an hour), for our client id, from Google's issuer, not expired. If the keys cannot be
  fetched nobody signs in. The claims the signature cannot vouch for (this sign-in's `nonce`, `email_verified`, the domain) are still checked.
- **Our own session tokens** are HMAC-SHA256 over a JSON payload (standard library). They carry `ver`, the person's `session_version` when issued;
  logging out adds one, which ends every session. A token issued before versions existed has none and counts as version 0. Changing
  `SECRET_KEY` still signs everyone out at once. Only the one-time codes and the version number are in the database.
- **Rate limits per login** (`security/rate_limit.py`): each signed-in person gets 300 calls a minute across the API and 6 bulk uploads a
  minute; each email gets 10 Google sign-ins in 10 minutes (`/login?error=too_many_attempts`). Counters are in memory per worker, so the real
  ceiling is up to double; nginx adds a per-visitor-address limit (see `docs/DEPLOYMENT.md`).

## Not built yet

- Trying it against real Google needs the OAuth client and the settings; see `docs/DEPLOYMENT.md`.

Tests: `server/tests/test_google_auth.py` (the flow; Google's answers are faked and the signature check is switched off there),
`test_google_signature.py` (the signature check, with real RSA keys), `test_logout.py`, `test_rate_limit.py`, `test_security_surface.py`.
