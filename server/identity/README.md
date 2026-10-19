# identity

Who exists, who is on which team, who runs it, and who can sign in. Everything is under `/api`.

Rules in one paragraph: the directory (people) comes from Slack. A person has a team role (`member` or `manager`) and, separately, an `is_admin` flag. Only active managers and admins can sign in. An admin creates teams (each starts with one person, who becomes its manager), changes managers, deletes teams, and can add or remove people on any team. A manager adds and removes people on their own team. An admin who is also a member or manager keeps both. Every team or membership change is written to an append-only audit log (a database trigger refuses `UPDATE` and `DELETE` on it); admin changes require a reason. The tasks feature writes to the same log: `task.delete` (a snapshot of the deleted task and its timeline, since the timeline goes with the task) and `task.reassign`.

## Endpoints

| Method and path | Who | File | What it does |
| --- | --- | --- | --- |
| `GET /api/health` | anyone | `server/main.py` | Liveness check. |
| `GET /api/me` | signed in | `routers/people.py` | The signed-in person, with team name. |
| `GET /api/dev/accounts` | nobody (dev only) | `routers/dev.py` | The dev login's account list: every active admin and manager, then up to two plain members flagged `can_sign_in: false` so the refusal can be shown. A 404 `not_found` unless `DEV_AUTH` is on, so it does not exist in production. |
| `GET /api/people?unassigned=&admins=&q=&limit=&offset=` | signed in | `routers/people.py` | One page of the directory for the "Add person" and "Add admin" pickers and the admins list: active people, optionally only those on no team (never managers) or only those with admin access (on a team or not), filtered by name or email (`%` and `_` match literally). Paged, see below. |
| `PATCH /api/people/{id}/admin` | admin | `routers/people.py` | Make or revoke admin. Body `{is_admin, reason}`. Refuses a no-op and the last active admin. |
| `GET /api/audit-log?limit=&offset=` | admin | `routers/people.py` | One page of audit entries, newest first. Paged, see below. Each entry carries `actor_name`, `person_name` and `team_name`, looked up when the page is built (`audit.names_for`); a deleted team keeps its name from the entry's `details`, and a person who no longer exists is `null`. |
| `GET /api/teams` | signed in | `routers/teams.py` | Admin: every team. Manager: only their own. |
| `POST /api/teams` | admin | `routers/teams.py` | Create a team. Body `{name, initial_manager_person_id, reason}`. The person becomes manager. Returns 201. |
| `DELETE /api/teams/{id}` | admin | `routers/teams.py` | Delete a team for good. Body `{confirm_name, reason}`. Members go back to no team; the manager returns to member. Returns 204. |
| `PATCH /api/teams/{id}/manager` | admin | `routers/teams.py` | Make another person the manager; the old one becomes a member and stays on the team. Body `{person_id, reason}`. |
| `GET /api/teams/{id}/members` | admin, or that team's manager | `routers/teams.py` | People on the team, manager first. |
| `POST /api/teams/{id}/members` | admin, or that team's manager | `routers/teams.py` | Add a person who is on no team. Body `{person_id, reason}`; the reason is optional. Returns 201. |
| `DELETE /api/teams/{id}/members/{person_id}` | admin, or that team's manager | `routers/teams.py` | Take a person off the team (the dustbin). Optional body `{reason}`. The manager cannot be removed. Returns 204. |

Sign-in: with `DEV_AUTH=true` the caller is named by the `X-Dev-User-Email` header (local only). Otherwise every route except `/api/health` answers 501 `auth_not_configured` until Google sign-in is built.

## Paging

`/api/people` and `/api/audit-log` are paged on the server (the database applies `LIMIT` and `OFFSET`; nothing is sliced in the client). Query parameters: `limit` (1 to 200, default 50) and `offset` (0 or more). A value outside those ranges, or not a whole number, is refused with 422; it is never silently changed. The reply is:

```json
{ "items": [ ... ], "total": 262, "limit": 50, "offset": 100 }
```

`total` counts every match for the filters, not just this page, so a UI can show "101 to 150 of 262". An `offset` past the end returns `items: []` with the same `total`. Order is fixed: people by name then id, audit entries newest first then id, so equal names or equal timestamps never repeat or skip between pages. Teams and a team's members are not paged: there are a handful of teams and a team has tens of people at most. Limits live in `states.py` (`DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`).

## Errors

Every failure is `{"detail": {"code", "message"}}`; match on `code`.

| Status | Codes |
| --- | --- |
| 401 | `not_authenticated` |
| 403 | `domain_not_allowed`, `not_onboarded`, `forbidden` |
| 404 | `team_not_found`, `person_not_found`, `not_on_team` |
| 409 | `team_name_taken`, `person_inactive`, `already_manager`, `already_on_team`, `same_manager`, `person_unavailable`, `is_manager`, `admin_unchanged`, `last_admin` |
| 422 | `reason_required`, `reason_too_long`, `name_required`, `confirmation_mismatch`, `invalid_input` (text the database cannot store, such as a NUL character; any endpoint, nothing is written). A malformed body, id or paging value is also 422, but in FastAPI's own shape (`detail` is a list), not `{code, message}`. |
| 501 | `auth_not_configured` |

## Folder map

```
server/identity/
├── routers/
│   ├── __init__.py        assembles the one `router` (teams + people)
│   ├── teams.py           team and member endpoints
│   ├── people.py          /me, /people, admin toggle, audit log
│   └── dev.py             /dev/accounts (only while DEV_AUTH is on)
├── services/
│   ├── lookup.py          get_team / get_person (queries, 404 if missing)
│   ├── teams.py           list_teams, get_team_with_count; create_team, change_manager, delete_team
│   ├── members.py         list_members, get_member; add_member, remove_member
│   ├── admin_access.py    set_admin
│   ├── directory.py       search_people (the picker, one page + total)
│   ├── dev_accounts.py    list_dev_accounts (the dev login's list)
│   └── audit.py           record, clean_reason, list_entries (one page + total)
├── schemas.py             request and response models
└── states.py              audit action names
```

Shared code used here, kept outside the feature: `server/models/` (tables), `server/security/` (`authentication.py` who is calling, `authorization.py` what they may do), `server/database/`, `server/core/` (settings, `AppError`), `server/migrations/` (Alembic).

## Conventions

- **Command-query separation.** A service function either changes data (a command: checks, writes, records the audit row, commits once, returns nothing) or reads data (a query: changes nothing). A router runs the command, then a query to build the response. A command that creates something takes the new id from the caller.
- Permission rules live in `security/authorization.py` and nowhere else (the client has no copy; it reads what the API says). Change a rule there with a test.
- The database also enforces what it can: unique team manager, unique lowercase team names, one manager-role person per team, and an append-only audit log (a trigger refuses `UPDATE` and `DELETE`). The rule "a team's manager is on that team" is enforced by the services and tested, not by a trigger.

## Not built yet

- Google sign-in (last): `GET /auth/google`, `GET /auth/google/callback`, `GET /auth/google/exchange?code=`, a new `server/auth/` feature; planned in `docs/DEPLOYMENT.md` and `docs/WORKLOG.md` (step 9).
- The weekly Slack pull to refresh the directory (Phase 2); today the directory loads from `PEOPLE_FILE` (default `seed/people.json`) with `make db-seed`.

Tasks are built (`server/tasks/README.md`): a removed person's open tasks show as "needs a new owner", and a deleted team takes its tasks with it.

Tests: `server/tests/README.md`.
