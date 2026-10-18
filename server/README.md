# Work Board server

FastAPI + PostgreSQL. Today it holds three features: `identity/` (people, teams, admin; see `identity/README.md`), `tasks/` (the board, tasks, comments, the report; see `tasks/README.md`) and `auth/` (Google sign-in; see `auth/README.md`). Why Postgres: `docs/DATABASE_DECISION.md`.

## Quick start (from the repo root)

```bash
cp .env.example .env                     # then set POSTGRES_PASSWORD and BOOTSTRAP_ADMIN_EMAILS in it
make server-install                      # server/.venv + dependencies
make db-up                               # dev Postgres on 127.0.0.1:5436
make db-migrate                          # Alembic migrations
make db-seed                             # PEOPLE_FILE (default seed/people.json) + first admin (BOOTSTRAP_ADMIN_EMAILS from .env); skipped with a note if the file is missing
make api-dev                             # API on :8000, dev sign-in stub on
make server-test                         # tests (use their own database)

# Production (docker-compose.yml: database + API; migrations run on start; no seeds, no dev sign-in)
make prod-up                             # build, start, then load PEOPLE_FILE if present; make prod-down / prod-logs
```

The server reads only environment variables, never the `.env` file. `make` loads `.env` for the host targets and builds `DATABASE_URL` from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and `POSTGRES_PORT`; docker compose builds the containers' own `DATABASE_URL` from the same values. `DATABASE_URL` and the password have no default, so no credentials live in the code. The settings are listed in `.env.example`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | none (required) | Connection string. Built by `make` / compose from the `POSTGRES_*` values in `.env`; set it in `.env` only to override. |
| `DEV_AUTH` | `false` | `true` lets the caller be named by an `X-Dev-User-Email` header. Local only; off means Google sign-in only. |
| `ALLOWED_EMAIL_DOMAIN` | `atimotors.com` | The one company domain, checked at sign-in and when loading people. |
| `BOOTSTRAP_ADMIN_EMAILS` | empty | First admins, made by `make db-seed`. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | empty | From the Google Cloud OAuth client. All three plus `SECRET_KEY` are needed, or Google sign-in is "not set up" (`/auth/google` goes back to the login page with `oauth_not_configured`; with `DEV_AUTH` off, protected routes answer 501). |
| `SECRET_KEY` | empty | Signs session tokens and the sign-in cookie; at least 32 characters (`openssl rand -hex 32`). Changing it signs everyone out. |
| `TOKEN_TTL_SECONDS` | `28800` | How long a session lasts (8 hours). |

## Layout

```
server/
├── main.py            app, error handler, routes under /api
├── core/              settings, AppError
├── database/          engine, session, Base
├── models/            people, teams, access_audit_log, tasks, task_activity
├── security/          authentication (who), authorization (what they may do, the allowed task moves)
├── identity/          the feature: routers, services, schemas, states
├── tasks/             the feature: routers, services, rules, schemas, states
├── auth/              Google sign-in: the three /auth/google endpoints, signed session tokens, one-time codes
├── migrations/        Alembic; the schema comes only from here
└── tests/             see tests/README.md
```

Change the schema with a new Alembic revision (`cd server && .venv/bin/alembic revision -m "..."`), then run `alembic upgrade head` and `alembic check`. The tests build their database from the migrations.
