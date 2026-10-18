# Work Board: what has been built (developer view)

An internal tool for ATI Motors: a managers-only task board. Full product scope is in `plan/PLAN.md`; this page lists the engineering that is in the repo, where it lives, and how it is checked. Every claim here points at a folder or file.

## Stack

React + Vite + TypeScript, TanStack Query, React Router, dnd-kit, Tailwind v4 on the AtiUI design system; FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16; Docker Compose for dev and production.

## Backend (`server/`)

| Feature | Where | Notes |
|---|---|---|
| Feature-folder architecture | `server/identity`, `server/tasks`, `server/auth` | Routers, services, schemas and states per feature, each with a README listing every endpoint |
| Command-query separation | `server/*/services/` | A command checks, writes, commits once and returns nothing; a query only reads |
| One home for permissions | `server/security/authorization.py` | Roles, board access and every status transition rule; the UI only reads the `actions` the API returns |
| People, teams, managers, admins | `server/identity/` | One team per manager, one team per person; admin is a separate flag; last admin cannot be removed |
| Append-only audit log | `server/models/`, migrations | A database trigger refuses updates; team, membership, admin, task delete and reassign are recorded; deleting a team keeps one snapshot per task (`server/tasks/services/deletion_audit.py`) |
| Tasks, timeline, comments | `server/tasks/` | Status moves with reasons and remarks, a timeline and comments in one append-only table, delete and reassign rules |
| Late completion | `server/tasks/services/commands.py` | A "completed on" day (from the due date, once passed, to today) becomes the closed date so reports and on-time rate stay true |
| Board and report queries | `server/tasks/services/queries.py`, `report.py` | Filters, "needs attention", per-person counts, team and all-teams reports |
| Google sign-in | `server/auth/` | Signed session tokens and one-time codes; `@atimotors.com` only; Google is faked in tests (not yet tried against real Google) |
| Migrations | `server/migrations/` | The schema comes only from Alembic; a test checks them |
| Settings | `server/core/` | Environment variables only; no secrets in code |
| Tests | `server/tests/` | 555 pytest tests on a real Postgres test database |

## Frontend (`client/`)

| Feature | Where | Notes |
|---|---|---|
| Template architecture | `client/ARCHITECTURE.md` | `services/` owns network calls, wire-to-app mappers, query-key helpers, central 401 handling |
| Kanban board | `client/src/features/board/` | Drag and drop, filters as removable chips, "needs attention", task detail sheet with timeline and comments |
| Reason and remarks dialogs | `features/board/components/ReasonDialog.tsx` | Required reasons for block, send back, reopen, move back; remarks and a "Completed on" date for Done |
| Team report, CSV and PDF export | `features/board/components/ReportDialog.tsx`, `features/board/pdf.ts` | The PDF is drawn light from a copy of the page, so the live theme never changes |
| My team | `client/src/features/team/` | Add people from the directory with server-side search, remove with the dustbin |
| Admin portal | `client/src/features/admin/` | Teams, admins and audit log tabs; create and delete teams, change manager, make or revoke admin |
| Admin's read-only boards | `features/board/BoardView.tsx` | Any team's board, no actions; admins can still comment |
| Error boundaries | `client/ARCHITECTURE.md` ("Error boundaries") | One page-level and five panel-level boundaries; a failing panel does not blank the page; tested |
| Dark and light themes | `client/src/app/lib/theme.tsx`, `styles/globals.css` | Token swap, no `dark:` variants |
| Searchable dropdown | `app/components/ui/select.tsx` | Typing always reaches the search box; arrow keys still work |
| Design system | `app/components/ui/` | AtiUI components, Phosphor icons, tokens only (checked by a grep in the project rules) |
| Tests | `client/src/**/*.test.ts(x)` | 45 vitest tests |

## Operations

| Feature | Where |
|---|---|
| Local dev stack with a demo world | `make dev`, `docker-compose.dev.yml`, `seed/demo_db.py` |
| Production stack (database and API, no dev sign-in) | `docker-compose.yml`, `Dockerfile.api`, `make prod-up` |
| Directory loader with safety limits | `seed/load_db.py` (never deactivates an admin; refuses large removals without a flag) |
| Deployment notes | `docs/DEPLOYMENT.md` |
| Decision records | `docs/DATABASE_DECISION.md`, `docs/WORKLOG.md` |

## Not done yet

Browser pass in light and dark, component tests for the new screens, Playwright, server coverage pass, real Google sign-in, nginx and HTTPS, Slack bot (Phase 2). Details: `refdocs/checklist.md`.
