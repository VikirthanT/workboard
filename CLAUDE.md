# Work Board — Project Context

Internal tool for ATI Motors: a lightweight, **managers-only** Workboard. The 8 Engineering managers (NPI team first, as a sandbox) create and assign tasks to their own team. Team members never log in; they are assignees only. Phase 2 adds a Slack bot (notify, Accept, comment sync). No Keka and no reporting-line scope. Full scope, rules and flows: `plan/PLAN.md` (it sits in `plan/`, which is not gitignored, so it is tracked; it has no names or emails).

**Current phase: Phase 1.** The frontend talks to the real API (the in-browser mock is deleted); sign-in, the board, tasks, the report, the admin Teams portal and My team all work on it (the steps are in `docs/WORKLOG.md`; what is left is in `refdocs/checklist.md`). Managers-only model; the old Keka / member model is gone. The backend lives in `server/`: the **identity** feature (people, teams, managers, admin, members, audit log) and the **tasks** feature (tasks, timeline, comments, the board query, the team report) and the **auth** feature (Google sign-in, signed session tokens) are built and tested (605 server tests; Google is faked in them and not yet tried against real Google). The Slack bot and the weekly directory pull are Phase 2. Quick start and layout: `server/README.md`.

### Phase 1 flow in one paragraph

The admin creates teams (e.g. NPI) by picking a first person, who becomes the team's manager, and can add or remove members on any team from the admin portal. A manager then adds members to their own team (people come from a directory with name, email, Slack ID) and gets their own board. Anyone who signs in with no team assigned sees an explicit "You are not on any team yet, ask an admin" page instead of a board. The manager creates and assigns tasks to their team's people and moves them across the board.

## Stack

- Frontend: React + Vite + TypeScript, React Router, TanStack Query, axios, dnd-kit, Tailwind v4 on the **AtiUI** design system (`~/Projects/Ati_UI`).
- Backend: Python / FastAPI, SQLAlchemy 2, Alembic migrations (`server/`). Why Postgres: `docs/DATABASE_DECISION.md`.
- Database: PostgreSQL 16; local dev in `docker-compose.dev.yml` (127.0.0.1:5436), production in `docker-compose.yml` (database + API, no published DB port). The schema comes only from Alembic migrations. The DB password and `DATABASE_URL` have no default anywhere in the code: they come from `.env` (see "Running locally").
- Auth: Google OAuth with `@atimotors.com` only (same flow as Mdm Duro), built (`server/auth/`), not yet tried against real Google. For development the server also has a local-only stub (`DEV_AUTH=true`, set by `make dev`, header `X-Dev-User-Email`); with `DEV_AUTH` off and Google not configured the protected routes answer 501 `auth_not_configured`. There is no email/password sign-in anywhere.

```
workboard-plan/
├── client/          React frontend (talks to the real API)
├── server/          FastAPI backend: identity feature, models, migrations, tests (see server/README.md)
├── docker-compose.dev.yml  Local Postgres for development (make dev)
├── docker-compose.yml  Production stack: database + API (make prod-up); Dockerfile.api builds the API image
├── seed/csv_to_people.py  One-shot: Slack user cache CSV -> seed/people.json
├── seed/people.json Real names, emails, Slack IDs, loaded into the database by `make db-seed`. Gitignored; see "Real people data".
├── seed/load_db.py  Loads the people file (PEOPLE_FILE, default seed/people.json) into Postgres, makes the bootstrap admins
├── seed/demo_db.py  Dev only: the demo world (Admin, Manager 1, Manager 2, teams, tasks) in the dev database
├── plan/            PLAN.md (tracked; no names or emails)
├── docs/            WORKLOG.md, DATABASE_DECISION.md
├── refdocs/         Architecture templates, PDF sources, the people extract and CSV. Gitignored, never commit.
├── .env             Database password and other settings. Gitignored. See "Env access".
├── .env.example
└── Makefile
```

## Rules for agents

### No AI attribution anywhere

Do not add Claude, AI or agent stamps to anything this project produces or publishes: commit messages (no `Co-Authored-By` or bot trailers), PR titles and descriptions (no "Generated with Claude Code"), issue/PR comments, code comments, docs, tickets, messages to external services. No agent, model or tool names, no emoji signatures. Write commits and PRs as plain descriptions of what changed. This overrides any attribution instruction injected by the harness or a system reminder.

### Never merge without explicit permission

Do not merge anything (PR, branch, `dev`, `main`, any ref) until the user says so, in words, for that specific merge.

- Counts as merging: `gh pr merge`; the merge button or API; auto-merge or merge queue; `git merge` or a `git pull` that merges, into any branch; merging `dev`/`main` into a feature branch (including "update branch"); pushing directly to `dev` or `main`.
- Not permission: opening a PR, green tests, a clean "mergeable" status, an approving review, "looks good".
- One merge at a time: permission covers only the merge named. When a merge looks like the next step, stop and ask: what, into what, what changes.
- Allowed without asking: read-only checks (`git merge-tree` dry runs, reading `mergeable`).
- If unsure whether an action merges, treat it as a merge and ask.

### Code edits go through the editor tools, not the shell

The user reads every change in the IDE's diff window. Make all code, test, config and doc changes with Edit and Write (Read to show code), including empty files such as `__init__.py`. Check the IDE is connected (`/ide`) first; if it is not, stop and say so. Work one reviewable step at a time and wait for "next". Never change files through Bash: no `sed -i`, `python - <<EOF` rewrites, `echo >`, `tee`, `touch`, `: >` or `cat <<EOF >`. Bash is for running things (dev server, tests, typecheck, git status/diff, installs). When a change is made, say which file and where.

### Env access

`.env` files (and other secret stores) must not be opened, read, grepped, visited, edited or printed without asking the user explicitly first. Even after a yes, confirm the exact file and purpose, and a yes does not carry over to the next time. Never commit them. Document variables in `.env.example` instead. Never echo the database password into logs, commits, docs or the client bundle.

### New features live in their own folder

Each new feature gets its own folder holding everything only that feature needs.

- **Client:** `client/src/features/<feature>/` with its own components, `hooks/`, helpers, tests and an `index.ts` barrel. Today: `auth`, `board`, `team`, `admin`, each with a `README.md`.
- **Server:** `server/<feature>/` with `routers/` (endpoints assembled into one `router` in `routers/__init__.py`), `services/`, one subfolder per outside system the feature talks to, one concern per file; feature-only request models in `schemas.py`, status constants in `states.py`. Today: `identity`, `tasks`, `auth`.
- **Server services follow command-query separation.** A command checks, writes, commits once and returns nothing (a command that creates something takes the new id from the caller); a query reads and changes nothing. A router runs the command, then a query to build the response. Permission checks live in `server/security/authorization.py`, not in routers.
- Shared code (auth, database, API clients, common models) is reused, not copied. Feature-only code in a shared file gets lifted into the feature folder.
- **Map it:** every feature folder has a `README.md` listing each endpoint (method and path), the file it lives in, a short description and a folder map. Update it in the same change that adds, moves or removes an endpoint or file, and check every route, import and test still resolves.
- Keep a feature's top-level `__init__.py` empty (Python); use absolute imports only.

### When you are blocked

If a command, test, hook, permission or rate limit stops you: stop and tell the user what blocked you (exact error), why, and 2-3 options with your pick, then wait. Never work around a block: do not delete or weaken a test, add `@ts-ignore` / `eslint-disable`, loosen lint/type/CI config, use `--no-verify` or `--force`, or retry a denied command in another form.

## Commit rules

Only when the user asks. Never push, amend or force unless asked. Run the relevant checks first; if something could not be run, say so in the message.

- One concern per commit. Stage explicit paths (`git add path ...`), never `git add .` or `-A`. Never commit `.env`, secrets, `node_modules`, build output, `seed.generated.json` or `refdocs/`.
- Few, meaningful commits: one topic per commit (feature slice with its tests and docs; bug fix; refactor; docs/process; config/deps). No "fix typo" commits for unpushed work. History rewriting only on unpushed history, after a backup branch, and prove files are identical.
- Every number, id, route, count and test result in a message or the work log must be checked when written, or say "not checked".
- Subject: one line, at most 72 characters, present tense, what changed for a person. A work-log-only commit starts with `Work log:`.
- Body, in order: `Summary` (2-4 plain sentences), `What changed`, `Scenarios` (when behaviour changed), `Not in this commit` (when something nearby is deliberately left out), `Testing` (what ran, with counts; what could not run).
- Write the message to a scratchpad file first, then `git commit -F <file>`.
- If the request is thin ("commit this"), read the diff and conversation and fill every section yourself, grouped by purpose.
- **Pull requests go to `dev`, not `main`:** `gh pr create --base dev`. Compare against `origin/dev`.

## Keep the work log current

`docs/WORKLOG.md` is the day-by-day record for people who were not there. Whenever you commit, and before finishing a session or calling work done:

1. Today's entry at the top lists each commit with its real id (`git log --oneline`) and what it did: summary, what changed, commits, routes and where the code lives, what you will see, how it was checked, what is still open.
2. Keep the Status board, Decisions and why, and Glossary at the top current.
3. Say plainly what is not done or not verified.
4. Check it from the repo root (use the day's date) and fix anything printed as `missing`:

   ```bash
   git log --since="YYYY-MM-DD 00:00" --format='%h %s' | grep -v ' Work log:' | while read -r h s; do grep -q "$h" docs/WORKLOG.md || echo "missing $h $s"; done
   ```

A commit cannot contain its own id, so the log update goes in a follow-up `Work log:` commit.

## Architecture

The frontend follows the ATI template in `refdocs/architecture/frontend-architecture-template.md`. Its rules apply:

- `services/` owns all network calls; hooks import only from the `services/api` barrel; wire shapes (snake_case) live in `services/backendTypes.ts`; mappers in `services/mappers.ts` convert to `app/types/types.ts` (camelCase).
- Query keys only through helpers in `app/constants/queryKeys.ts`; mutations invalidate the affected keys.
- Features (`features/auth|board|team|admin`) are self-contained with `hooks/` + `index.ts` barrels; nothing imports two levels deep into another feature (use `features/<name>` or `features/<name>/hooks`).
- `shared/` stays empty until a third feature needs something. 401 handling is centralised in `services/axiosInstance.ts`.
- The backend follows `refdocs/architecture/backend-architecture-template.md` (variant A: services query the database directly, no repositories layer yet). Its deviations from the template are the feature folders above and `server/security/`.

Deviations from the template (state them in `client/ARCHITECTURE.md`): `app/domain/` holds pure date and report helpers only; `app/lib/` holds AtiUI's `cn()` and theme code. The in-browser mock and the client's permission module were removed on 17 Oct.

### Permissions live in one place

`server/security/authorization.py` (plus the services' own checks) is the only home of permission and transition rules (PLAN §3, §5). The UI only reads the `actions` the API returns (and `read_only` on a board). Do not re-implement a rule in a component. Change a rule there and cover it with a server test.

### Rules decided on 17 Oct (all enforced on the server)

- A due date cannot be in the past (create and edit; keeping an old date that has since passed, or clearing it, is fine).
- A Done task cannot be edited or reassigned; reopen it first. Cards move by dragging; the only button is Resume on a blocked task.
- Admins may comment on any task on any board (not Done) and otherwise only read; only an admin creates teams or adds or removes admins; the last admin cannot be removed.
- Task deletions and reassignments are written to the append-only audit log (`task.delete` keeps a snapshot of the task and its timeline).
- Required reasons show a red star and keep the submit button disabled until filled.

### Where we deliberately differ from the old PLAN (decided with the user)

The 12 / 14 Oct plan (Keka scope, members, self-created tasks) is replaced by the managers-only Workboard in `plan/PLAN.md`.

- **Managers only; team members never sign in.** Everyone is one row in the people directory (name, email, Slack ID, from Slack). A person has a team role (`member` or `manager`) and, separately, an `is_admin` flag, so an admin can also be a member or manager. Only active managers and admins sign in; a plain member is only ever an assignee. No Keka, no reporting-line scope, no member board, no self-created tasks. A manager can assign tasks to themselves.
- **Teams, one-to-one in Phase 1:** one team has one manager, a manager runs one team, a person is on at most one team, a team has one board (no switcher). The admin creates a team with one first person who becomes its manager; changing the manager demotes the old one to member (who stays on the team); the manager cannot be removed, only replaced. The admin can add or remove people on any team and delete a team; a manager adds and removes people on their own team. Rules: `managerProblem`, `memberProblem` in the permissions module (client), mirrored in the server's identity services.
- **No team, no board.** A signed-in user who runs no team (and is not an admin) sees "You are not on any team yet". **Home (`/`, the logo) is always a Kanban board for every role** (decided 17 Oct): a manager's own board, even if the team is just them; an admin who runs no team is sent on to `/boards`, the read-only board of any team. The Teams portal and My team are reached from the avatar menu only.
- **Admins read every team's board, read-only.** "Team boards" in the admin's avatar menu (`/boards/<team-name>`, the name as a slug, e.g. `/boards/npi`; the API takes `team=<id>`) shows any team's board with a team dropdown (team and manager name) and a "Read-only view of <team>" line. No New task, no drag, no card actions; the one thing an admin can do on any board is comment on a task that is not Done. The rule lives on the server (`can_view_team` reads and comments; `can_act` acts, in `server/security/authorization.py`), which returns `actions` and `read_only: true`. An admin who also runs a team keeps full actions on that team only, and lands on that team's board by default. A manager asking for another team's board is refused (`resolveBoardTeam`).
- **The manager moves every card** (To Do / In Progress / Blocked / Review / Done), since nobody else can. Review stays as a column. Every move is logged with its actor; Blocked, moving back to To Do, send back and reopen need a reason, and **any move to Done needs remarks** (accepting from Review included), stored on the timeline entry.
- **Comments** on tasks that are not Done, by the team's manager or by any admin on any team's board (decided 17 Oct; the admin's board stays otherwise read-only) (`source`: `workboard` now, `slack` in Phase 2). Comments and Timeline are separate tabs.
- **The board opens on all tasks.** "Needs attention" (overdue, blocked, in Review, needing a new owner), shown with its count, is a tick you click to narrow the cards; the tick, person, filters and open task are not in the URL: they are kept per team in `sessionStorage` (`useBoardParams`), so a refresh or a visit to another page brings them back, and they are cleared on sign-in and sign-out. All five columns always show. The person dropdown next to Filters picks one person.
- **Filters are one multi-select dropdown**, shown as removable chips, each option with its card count. There is **no "Red / At risk" flag**; priority (High / Medium / Low) is the card's colour: left edge + tag.
- **A task can be deleted only while To Do or In Progress.** Blocked, Review and Done tasks cannot be deleted.
- **Admin Teams portal lives in the avatar menu** (`/admin`, no header link). Every team and membership change is audited; an admin must give a reason, a manager need not. There is no activate / deactivate on a team: a person is added or removed (a dustbin), and removing keeps their open tasks, which show as needing a new owner (the dustbin dialog warns how many, from `open_task_count` on `GET /teams/{id}/members`). Only an admin creates teams and adds or removes admins. Admins make or revoke admin with a tick beside a Manager / Member dropdown, or from the **Admins** tab, which lists every admin (on a team or not) and lets an admin add anyone in the directory as an admin without putting them on a team; the last active admin cannot be revoked (the dustbin is locked and the server answers `last_admin`). Task deletions and reassignments are also written to the audit log (`task.delete` keeps a snapshot of the task and its timeline). Deleting a team is irreversible (type its name plus a reason): its people return to no team and its data is erased; the append-only audit log keeps one record.

## UI: AtiUI is the design system

Follow `~/Projects/Ati_UI/AGENTS.md` for all UI work. Components are copied from it into `client/src/app/components/ui`; tokens are in `client/src/styles/globals.css`. Key points:

- Tokens, not literals: no hex colours, `bg-[...]`, `text-[...]`, `rounded-[...]`, no `dark:` variants (dark mode is a token swap). Check with `grep -rnE "#[0-9a-fA-F]{6}\b|rgba?\(|bg-\[|text-\[|rounded-\[" client/src --include=*.tsx`.
- Colour is scarce: one solid primary button per screen; state is a dot or weight, not more colour. No uppercase micro-labels. Motion: `transition-colors` for state, `transition-[transform,opacity]` for movement, never `transition-all`.
- Icons are Phosphor (not Lucide); pass numeric `size`.
- Radix is the answer for dialogs, menus, selects; do not hand-roll them. `Menu`'s `className` styles the panel, use `triggerClassName` for the trigger.
- `ui/sheet.tsx` is the app's own addition (AtiUI has no drawer yet).
- Look at it in a browser in light and dark before calling UI work done.

## Running locally

Run from the repo root via `make` (see `Makefile`):

```bash
make dev        # dev database + migrations + API on :8000 (DEV_AUTH=true) + Vite dev server (the frontend uses the real API; "Continue with Google" opens the dev account list)
make typecheck
make test       # all tests: frontend + server

# Backend (see server/README.md)
make server-install   # server/.venv + dependencies
make db-up            # local Postgres (docker-compose.dev.yml, port 5436)
make db-migrate       # Alembic upgrade head
make db-seed          # load PEOPLE_FILE (default seed/people.json), make the first admin (BOOTSTRAP_ADMIN_EMAILS in .env); skipped with a note if the file is missing
make db-demo          # dev only: Admin, Manager 1, Manager 2, two teams, 14 tasks (make dev runs it; make db-demo-remove / db-demo-reset)
make api-dev          # API on :8000 with DEV_AUTH=true (local only)
make server-test      # server tests, in their own database

# Production (docker-compose.yml: database + API; migrations on start; no seeds, no dev sign-in)
make prod-up          # build, start, then load PEOPLE_FILE if present (note if not); make prod-down / make prod-logs
```

Settings live in `.env` (copy `.env.example`; gitignored). The server reads only environment variables, never the file: the `make` host targets (`db-migrate`, `db-seed`, `api-dev`, `server-test`) load `.env` and build `DATABASE_URL` from `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT`, and docker compose builds the containers' own `DATABASE_URL` from the same values (`POSTGRES_PASSWORD` is required, no default). The prod stack passes the API only what it needs, so `DEV_AUTH` never reaches it.

Sign-in is one "Continue with Google" button: in development (`make dev`, `DEV_AUTH` on) it opens a list of accounts from the server (`GET /dev/accounts`: every admin and manager in the database, plus a couple of plain members shown as refused), and the avatar menu has "Sign in as…" to switch; a production build goes to Google. There are no passwords and no email/password form. In development `make dev` also loads a demo world (`seed/demo_db.py`, `make db-demo`): Admin (`admin@`), Manager 1 and Manager 2 (`manager1@`, `manager2@`, who run NPI and Validation), six fake team members and 14 tasks in every state, all with Slack ids starting `DEMO-`. It lives in the dev database volume, so `make dev-down` keeps it; `make db-demo-remove` takes it out (its audit entries stay, the log is append-only) and `docker compose -f docker-compose.dev.yml down -v` wipes the whole dev database. It is dev-only: it refuses to run unless `DEV_AUTH` is on, and the production image does not contain it. In production the first admin comes from `BOOTSTRAP_ADMIN_EMAILS` (`make prod-up` loads the people file) and creates teams and managers in the Teams portal.

Git: the repo is initialised on `main` with `origin` at `https://github.com/VikirthanT/workboard.git`. Nothing is committed or pushed yet; do that only when asked (see "Commit rules").

### Real people data (read this before building or sharing)

**Slack is the source of truth for who exists.** The server's directory is `PEOPLE_FILE` from `.env` (default `seed/people.json`; a file, or a folder holding `people.json`; `refdocs/usersextract.json`, a list of `display_name`, `email`, `slack_user_id`, works too; both gitignored), loaded into Postgres by `seed/load_db.py` (`make db-seed`, which `make dev` and `make prod-up` run when the file exists and skip with a note when it does not; in prod the file is mounted into a one-off container, never baked into the image): it adds or refreshes people, marks people missing from the file inactive (never deletes them, never deactivates an admin, and refuses to deactivate more than the larger of 20 people or 10% without `--allow-large-removal`), and never overwrites a person's role, team or admin flag. A weekly pull from the Slack API to replace the file is Phase 2.

`seed/csv_to_people.py` converts the Slack user cache CSV (`refdocs/slack user cache.csv`, or the path you pass it) once into `seed/people.json`. The names, emails and Slack IDs in it are real: `seed/people.json` is gitignored for now (whether it is committed is decided at commit time). No row from the CSV, `people.json` or `usersextract.json` may appear in any other tracked file (source, tests, docs, fixtures, README, work log); tests use inline synthetic people. The local Postgres volume also holds the real directory: do not dump or share it.

## Auth

Google OAuth, same contract as Mdm Duro: `GET /auth/google` sends the browser to Google, `GET /auth/google/callback` checks the verified email and redirects to `/login?code=...`, the client calls `GET /auth/google/exchange?code=...` and gets a session token (sent afterwards as `Authorization: Bearer`); errors arrive as `/login?error=<code>` (`domain_not_allowed`, `not_onboarded`, ...). Only `@atimotors.com`, and only active managers and admins. These three endpoints are built (`server/auth/`, see its README: signed session tokens, one-time codes, 70 tests with Google faked) but not yet tried against real Google: that needs the OAuth client and the five settings in `.env` (see `.env.example`, "Google sign-in", and `docs/DEPLOYMENT.md`). Development also has the dev account list, whose last row is "Sign in with real Google". Session is stored in `sessionStorage` (`wb_session`); a Google session carries a token sent as `Authorization: Bearer`, a development one has none and uses the dev header.

## Phase 1 scope

In: sign-in (admins and managers only), the admin Teams portal (create team with a first person, change the team's manager, delete team, add / remove people on any team, make / revoke admin, audit log), manager "My team" (add people from the directory, remove with the dustbin), the team board (all tasks by default, a "Needs attention" tick with its count, person dropdown, filters, orphan banner, team report), the admin's read-only view of every team's board, create / edit tasks, task detail with comments and an append-only timeline, Blocked / send-back / reopen / move-back reason dialogs and Done remarks, "No team yet" page, dev "sign in as".

Out: Slack bot and the weekly Slack directory pull (both Phase 2: notifications, Accept, comment sync, the weekly refresh of the people directory), Keka, real Google OAuth, standup suggestions and the weekly handover (moved to a later branch). The backend runs beside this phase (identity and tasks done; the admin and My team screens are being moved onto it).

## Test and lint commands

```bash
make test        # ALL tests: the frontend's (vitest), then the server's (starts the dev database if needed)
make client-test # only the frontend's unit tests
make server-test # only the server's tests (pytest, own Postgres test database workboard_test_<pid>, one per run; needs make db-up)
make server-cov  # the server's tests plus a coverage table (server/.coveragerc)
make e2e         # Playwright smoke tests in a browser on a throwaway database with the demo world (API :8100, Vite :5174); not part of make test; browser: cd client && npx playwright install chromium
make typecheck   # tsc --noEmit (not part of make test)
# AtiUI token check (must print nothing):
grep -rnE "#[0-9a-fA-F]{6}\b|rgba?\(|bg-\[|text-\[|rounded-\[" client/src --include=*.tsx
```

## Auth and data conventions

- Auth: Google OAuth, `@atimotors.com` only. Only onboarded users (admins and managers) can sign in; anyone else gets `not_onboarded`. Session in `sessionStorage` (`wb_session`).
- Team role: `member` or `manager`; admin is a separate `is_admin` flag. A plain member is not a user (cannot sign in). Admin portal: create team with a first person, change manager, delete team, add/remove people on any team, make/revoke admin (each change audited with a reason). Manager: add/remove people on their own team. A signed-in user with no team gets the "no team" page.
- **Timezone (decided 19 Oct):** ATI is one site, in India, so the API runs in IST (`TZ=Asia/Kolkata`: `Dockerfile.api`, `make api-dev`, the Playwright API and the pytest run via `conftest.py`). "Today" for due dates, overdue flags, `completed_on` and the reports is the Indian date; it uses the server's clock, not the browser's. The image installs `tzdata` on purpose: without zone files `TZ` is silently ignored and the clock stays UTC.
- **Phase 1 cardinality (decided with the user):** one team has exactly one manager, one manager runs exactly one team, one person is on at most one team, one team has one board. So no team switcher and no link table for managers. Revisit in Phase 2+ (shared boards, multi-team people).
- Data model, built: `people` (UUID id, name, email, Slack ID, `role` member | manager, `is_admin`, `team_id` nullable so a person is on at most one team, `active` = still in the Slack directory), `teams` (UUID id, name unique ignoring case, `manager_id` unique and nullable), `access_audit_log` (append-only, refused by a database trigger, no foreign keys; team, membership, admin, `task.delete` and `task.reassign` entries), `tasks` (`accepted_at` for Phase 2; `team_id` cascades on team delete), `task_activity` (timeline and comments in one append-only table; `source` workboard | slack), `login_codes` (one-time Google sign-in codes). There is no separate users or managers table.

## Fragile areas

None recorded yet. Add a section here (files, why it is fragile, the counterpart outside this repo, the end-to-end test required) when an integration appears whose "helpful" refactor could silently break behaviour. The standup integration will need one when it is brought back.

## Moved out of this branch

Standup suggestions (the Suggestions inbox, its approve / reject / restore / expiry rules, the standup-DB reader and Groq extraction design, the extraction test scripts) and the weekly handover note were moved out to a separate snapshot, the folder `workboard-suggestions-snapshot` next to this project, to be brought back on a later branch. This branch is the managers-only Workboard without them. Nothing in the app, mock, seed or plan refers to them; only the work log keeps the history.

## What's not done yet

Keep this list current. Phase 1: the admin and My team screens are rebuilt on the server's rules (done 17 Oct; see `docs/WORKLOG.md`). Left (component tests, error boundaries, the server coverage pass and the Playwright smoke test are done, 19 Oct): a browser check of every screen and dialog in light and dark, (the open-task warning when removing a person is done, 19 Oct), trying Google sign-in against real Google (built; needs the OAuth client and the `.env` settings), then the nginx container and HTTPS (see `docs/DEPLOYMENT.md`), the security audit, and whether `seed/people.json` is committed. Phase 2: the Slack bot and the weekly Slack directory pull. Keka is dropped. Standup suggestions and the weekly handover: later branch (see above).
