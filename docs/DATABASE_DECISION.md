# Decision: PostgreSQL for the Work Board database

Status: decided and built. The backend runs on PostgreSQL 16 (schema only from Alembic migrations); the in-browser mock the first draft mentioned no longer exists.

## Question

Should the Work Board use "SQL" or PostgreSQL? Postgres is itself a SQL database, so the real question was Postgres versus a lighter or different SQL engine (SQLite, MySQL).

## Decision

Use PostgreSQL, accessed from FastAPI through SQLAlchemy and migrated with Alembic.

## Why

- **It is already the plan.** `CLAUDE.md` and `plan/PLAN.md` specify FastAPI + PostgreSQL, and the backend architecture template assumes it.
- **The data is relational.** Teams, managers, people, tasks, task activity, task comments and the access audit log all reference each other by foreign keys.
- **The Phase 1 rules map to constraints.** The database can enforce them in addition to the application checks in `server/security/authorization.py`:
  - one manager per team: unique `teams.manager_id`
  - one team per manager: the same unique constraint, from the other side
  - a person on at most one team: nullable `people.team_id`, a single column
- **Concurrent writers.** Several managers and, in Phase 2, a Slack bot write at the same time. SQLite allows one writer at a time; Postgres does not have that limit.
- **Flexible fields where needed.** JSONB suits audit details and Slack message metadata without a separate store. Partial and unique indexes cover rules such as "only one active manager per team".
- **Same stack as Mdm Duro.** The team already knows the tooling, deployment and operations.
- **Room to grow.** Phase 2+ may allow shared boards or people on several teams. That is a schema change in Postgres, not an engine migration.

## Alternatives considered

| Option | Verdict |
| --- | --- |
| SQLite | Fine for a throwaway prototype. Single writer and no network access make it a poor fit for a multi-user tool with a Slack bot. |
| MySQL | Would work, but adds nothing over Postgres and breaks consistency with the other ATI services. |

## Consequences

- Enforce every permission rule on the server as well as in the shared permissions module.
- Add the cardinality rules above as DB constraints, not only as application checks.
- Real people data (names, emails, Slack IDs) will live in this database; keep it out of tracked files and shared dumps, as described in `CLAUDE.md`.
- Revisit the one-to-one cardinality decision before Phase 2.
