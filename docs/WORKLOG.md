# Work log

Day-by-day record for people who were not there. Newest entry first. Commit ids are filled in when commits are made; nothing below is committed yet.

## Status board

| Area | State |
|---|---|
| Managers-only model (users vs people, teams, one-to-one cardinality) | Done; the rules live on the server only (`security/authorization.py`), 550 server tests |
| Admin Teams portal (`/admin`) | Rebuilt on the real API (17 Oct): grouped collapsible teams, search, role filter, Manager / Member dropdown, Admin tick, dustbin, create / delete team, paged audit log. Looked at in a browser, light and dark (Teams tab light, Audit tab dark); dialogs not yet clicked through; no component tests yet |
| Manager My team (`/team`) and "No team yet" page | My team rebuilt on the real API (search, add, dustbin); not yet looked at in a browser after the rebuild |
| Board (one per team) | On the real API; home for every role; drag to move (Resume button on a blocked task); admins may comment on any board; looked at in a browser, light and dark. Some of 17 Oct's changes (admin comments, delete / reassign audit) not yet looked at in a browser |
| Standup suggestions (inbox, lifecycle rules, standup-DB reader and Groq extraction design) and the weekly handover note | Moved out of this branch to the snapshot folder `workboard-suggestions-snapshot`, to come back on a later branch |
| Backend (FastAPI + Postgres) | Identity (people, teams, admin, audit), tasks (tasks, timeline, comments, board query, team reports) and auth (Google sign-in, signed tokens) built; 550 server tests pass (Google faked). The frontend talks to it for everything. Google sign-in not yet tried against real Google. |
| Local setup and production stack | `.env` (copy `.env.example`) drives `make dev` and `make prod-up`; the database password and URL are in no source file; `docker-compose.dev.yml`, `docker-compose.yml` (prod) and `Dockerfile.api` added |
| Slack bot and the weekly Slack directory pull (both Phase 2) | Not started; data model carries `accepted_at` and comment `source`; until the pull exists the directory loads from a file (`make db-seed`) |
| Frontend tests | 41 vitest tests on pure code (mappers, errors, report, people filter, audit text); `make test` also guards the production bundle. No component tests yet |
| Playwright specs | Not set up (ad hoc browser checks only) |
| What is left | `refdocs/checklist.md` is the working list for the coming days |

## Switch the frontend to the real API: steps

One part at a time; each part ends with `make typecheck`, `make test` and, once the server is involved, a check against the live API. Decided with the user on 17 Oct: the in-browser mock is not kept (it is never deployed), so the screens are built straight against the real server and tested with `make test` and the live API.

| # | Part | State |
|---|---|---|
| 1 | **Tasks wire contract.** Board, task, timeline and report shapes in `backendTypes.ts`, the mappers and the mock now equal the server's (`name` not `display_name`, `team_id`, nullable owner, slim board team). Contract test `services/mappers.test.ts`, plus a key-by-key comparison of the server's OpenAPI schemas with the wire types. | Done (17 Oct) |
| 2 | **Sign-in and `/me` on the real API.** The login page is one "Continue with Google" button. In development it opens a list of accounts served by the server (`GET /dev/accounts`, a 404 unless `DEV_AUTH` is on; admins and managers, plus a couple of plain members shown as refused); a production build goes to Google. The session sends `X-Dev-User-Email` in dev builds only. `Me` is built from `GET /me` + the team's people + the board's review count. The real API is now the default and Vite proxies `/api` to `:8000`. Server errors (`{code, message}`) are read correctly (`errorMessage`, `errorCode`). | Done (17 Oct), checked in a browser, light and dark |
| 3 | **Delete the mock.** Done (17 Oct, with the user's OK to `rm`): `client/src/mocks/` and `seed/seed.py` are gone, with the `VITE_USE_MOCK` flag, the mock sign-in chooser and "Reset demo data"; "Sign in as…" stays in dev builds, driven by the server's account list; `make dev` and `make build` no longer seed; the mock-only `reportCounts` and its tests were removed (the server's report tests cover the same ground). `app/domain/permissions.ts` and its test are gone too (checked 17 Oct: nothing imports them). | Done (17 Oct) |
| 4 | **Server gaps the screens need.** Open-task counts per team (the admin's team dropdown), and an open-task count per person for the remove warning. Decide where each lives (identity vs tasks) before writing it. | Not started (the remove dialog has no open-task warning until it exists) |
| 5 | **Teams and members on the new rules.** Create a team with a first person, change the manager, delete a team (type its name plus a reason), add a member (reason optional), remove only (no Active / Inactive). Services, hooks and dialogs on the server's shapes. | Done (17 Oct): `services/teams.ts`, `features/team`, `features/admin`. Fixed the `GET /api/teams/{id}` 405: that route never existed on the server |
| 6 | **Admin screens.** Manager / Member dropdown, the admin toggle (`PATCH /people/{id}/admin`), and the audit log in the server's shape (action codes, paged). | Done (17 Oct). The server's audit entries now carry `actor_name`, `person_name`, `team_name` |
| 7 | **Clean up and smoke test.** Docs, a browser pass in light and dark of every screen, one Playwright smoke test, error boundaries, component tests, a server coverage pass. | Docs done; the rest is in `refdocs/checklist.md` |
| 8 | **Production containers, HTTP only** (decided with the user: plan now, build when needed). An `nginx` container that serves the built frontend and passes `/api/` to the API, added to `docker-compose.yml`; tested over plain HTTP. What each container is, how it is built and why: `docs/DEPLOYMENT.md`. | Planned, not built |
| 9 | **Google sign-in.** A new server feature `server/auth/` (routers, services, schemas, states, README, tests) with three endpoints: `GET /auth/google` (to Google, with `state`), `GET /auth/google/callback` (verify the `@atimotors.com` email and that the person is an active manager or admin, then back to `/login?code=` or `/login?error=`), `GET /auth/google/exchange?code=` (one-time code for a signed, expiring session token). `get_current_person` also accepts `Authorization: Bearer`; the dev header stays dev-only. Settings: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SECRET_KEY`, `TOKEN_TTL_SECONDS` (in `.env.example`, in its own "Google sign-in" section, and passed to the prod container). You create the Google OAuth client (consent screen Internal) and add the redirect address; `http://localhost:5173/api/auth/google/callback` works for trying it locally with no domain. What it needs and why: `docs/DEPLOYMENT.md`; the feature: `server/auth/README.md`. | Built (17 Oct), 70 tests with Google faked. Not yet tried against real Google: waiting for the OAuth client and the settings in `.env` |
| 10 | **HTTPS**, last, once there is a domain (certbot, redirect, HSTS). Production Google sign-in needs it. | Later |

## Decisions and why

- **16 Oct: managers only.** The brief limits Phase 1 to the Engineering managers; team members never sign in. Keka, reporting lines, member boards and self-created tasks are removed.
- **16 Oct: one team has one manager, a manager runs one team, a person is on one team, one board per team (decided with the user, Phase 1).** Keeps suggestion routing and the board unambiguous. Revisit for shared boards or people on several teams.
- **16 Oct: admin creates teams, sets managers, can add people to any team; a manager adds people to their own team.** A signed-in user with no team sees "You are not on any team yet".
- **16 Oct: Review column kept; the manager moves every card.** Only the manager can act, so Review is a manager checkpoint until Phase 2.
- **16 Oct: suggestions and the weekly handover are moved out of this branch (decided with the user).** The MVP is the managers-only Workboard on a real backend first; the AI-assisted parts come back on a later branch from a snapshot copy. Their decisions (suggestion lifecycle, direct standup DB access, Groq first) live with that snapshot.
- **16 Oct: people directory is real data from the Slack user cache.** Converted once into `seed/people.json` (gitignored; committing it is decided at commit time). It lands in the gitignored `seed.generated.json`, so the mock build bundles real names: never deploy a mock build.

- **17 Oct: Done cards stay on the board (decided with the user).** The "leave after about a week" rule is removed everywhere; the Done column shows the most recently closed first, and reports never hid them anyway.
- **17 Oct: adding a team member needs no reason (decided with the user)**, from an admin or a manager. Removing a member and the other team changes keep their rules.
- **17 Oct: one `.env`, no credentials in code (decided with the user, after Mdm Duro).** `POSTGRES_PASSWORD` is required and has no default; `make` and docker compose build `DATABASE_URL` from the `POSTGRES_*` parts; the server itself still reads only environment variables. `DEV_AUTH` is not in `.env`: `make dev` and `make api-dev` set it, and the prod stack forces it off.
- **17 Oct: no demo passwords (decided with the user).** The mock's Google chooser lists every seeded user, so the email/password form and `SEED_*_PASS` are gone. The chooser also offers "Team Member" (not a manager or admin) and "Guest Visitor" (wrong domain) to demo the denials.
- **17 Oct: one people file (decided with the user).** `PEOPLE_FILE` in `.env` (default `seed/people.json`; a file, or a folder holding `people.json`) feeds both the mock seed and the database load. `make dev` and `make prod-up` load it when it exists and print a note when it does not.

## Glossary

- **User:** someone who signs in (admin or manager).
- **Person:** a people-directory entry (name, email, Slack ID). Never signs in; an assignee.
- **Team:** one manager, a set of people, one board.
- **Needs a new owner:** an open task whose assignee is inactive or no longer on the team.

## 19 Oct 2026: first commits, late completion, team-delete audit, small UI fixes

**Summary.** A task marked Done late can now say the day the work finished; deleting a team keeps one audit snapshot per task; a few UI fixes. The repo had no commits, so the whole project was committed on `main` (not pushed) in topic order.

**Commits (oldest first).**
- `c22ca93` Add project rules, plan and repo config
- `9e2bd3b` Add the server foundation: database, models, migrations, security
- `20cb407` Add the identity feature: people, teams, admins and the audit log
- `ef57f7d` Add the tasks feature: board, timeline, comments, reports, late completion (includes the team-delete audit snapshots)
- `6718cb5` Add Google sign-in and signed session tokens
- `99ca820` Add the dev and production stacks and the seed tools
- `7d9ce56` Add the client foundation: shell, services and design system (page-level error boundary)
- `0a35e06` Add the board, My team, admin portal and sign-in screens (panel-level error boundaries)
- `ed70f20` Add the developer feature list and deployment notes
- `199f735` Add the empty client shared barrel

Not committed on purpose: `.claude/`, `claude_template.md`, `.env`, `seed/people.json`, `refdocs/`.

**What changed.**
- Late completion: `POST /api/tasks/{id}/status` takes `completed_on` (server `tasks/services/commands.py`, `schemas.py`); the Done dialog (`features/board/components/ReasonDialog.tsx`) has a "Completed on" date (default today, from the due date once it has passed up to today) sent through `services/tasks.ts` and `useMoveTask`. Closed date and the timeline remark carry the day; the due date is untouched. 3 server tests.
- Team delete: `tasks/services/deletion_audit.py` writes the `task.delete` snapshot for each task (also used by the single-task delete); 1 server test.
- Avatar menu: "My board" for managers; admins who run a team see "Other teams' boards" (read-only), others "Team boards".
- The report PDF no longer flips the live page to light (`features/board/pdf.ts` switches only html2canvas's copy).
- Person dropdowns with a search box (`ui/select.tsx`): focus the box on open, and typing goes there even after the mouse or arrows are on the list; Add member and Add admin open the list with the dialog.

**Checked.** 555 server tests, 41 client tests, `make typecheck` and the AtiUI token grep all passed. Not checked: any of the UI changes in a browser (light and dark), the PDF in dark mode, the dropdown focus inside the dialogs.

**Open.** Bootstrap admins are re-granted on every `make db-seed`, so a revoked bootstrap admin comes back on the next `make dev` (decision pending).

## 17 Oct 2026 (latest): Teams and My team on the real API, the login page, dev code out of the production build

**Summary.** The admin Teams portal and the manager's My team page now run on the server's real endpoints, in the style of `refdocs/image.png`. Dev-only sign-in code no longer ships in the production bundle, and the login page was redesigned. Nothing is committed, so there are no commit ids.

**What changed.**
- Server: `GET /api/audit-log` entries carry `actor_name`, `person_name`, `team_name` (`identity/services/audit.py` `names_for`, `routers/people.py`); two tests in `tests/test_teams.py`; 533 server tests pass.
- Client services moved to the real routes: `services/teams.ts` (teams, members, create, delete, change manager, search unassigned, add, remove) and `services/admin.ts` (set admin, paged audit log). The old `/users`, `/audit`, `/people/unassigned`, `PATCH /teams/{id}` and member-active calls are gone, which fixes the `405` on `GET /api/teams/{id}`.
- Screens: `features/team` (`TeamSection`, `PeopleFilters`, `memberFilter`, `AddMemberDialog`, `RemoveMemberDialog`, `TeamMembersPanel`) and `features/admin` (`TeamsView`, `AuditLog`, `auditText`, `CreateTeamDialog`, `DeleteTeamDialog`, `PersonDialogs`). Teams have no Active / Inactive state any more; `BoardView` lists every team.
- Dev-only code: the account chooser is `features/auth/DevAccountChooser.tsx`, rendered only under `import.meta.env.DEV`; `getDevAccounts` and `devSignIn` throw outside dev; the request interceptor no longer overwrites an explicit `X-Dev-User-Email` (that was why "Sign in as…" showed the toast and changed nothing). A `bundle` suite in `make test` builds the production frontend and fails if a dev string is in it.
- Login page: one centred-left split (copy and a small sign-in card), larger wordmark, new headline.

**Decided with the user later the same day.**
- A due date cannot be in the past: refused on create and on edit (`due_date_past`, 422); keeping an old date that has since passed, or clearing it, is allowed; the picker disables past days. Two old tests were changed to match (the overdue filter test backdates a task in the database; the leap-day case uses 2028-02-29).
- Completed (Done) tasks cannot be edited or reassigned (`task_done`, 409; `can_edit` is false; the sheet says "Note: Completed tasks cannot be edited."). Reopen first. One old test that expected edits on a Done task was changed to the new rule.
- Task deletions and reassignments are written to the append-only audit log (`task.delete` with a snapshot of the task and its whole timeline, `task.reassign`), and show in the Audit log tab. Before this a deleted task left no trace. Edits stay on the task's own timeline only. A team delete still erases its tasks without a per-task record (only the team's `team.delete` row remains).
- Admins may comment on any task on any board (not Done); everything else on another team's board stays read-only. Five old tests that asserted "an admin cannot comment" were changed to the new rule. The admin's default page is unchanged: a manager who is also an admin opens their own team's board, an admin with no team opens the Teams portal.
- New **Admins** tab: lists every admin (on a team or not), "Add admin" picks anyone in the directory (no team needed), and the dustbin removes admin access. Server: `GET /people?admins=true`. Only an admin can add teams or add or remove admins, and the last admin cannot be removed (already enforced: `last_admin`; the UI also locks the dustbin).
- Home is always the Kanban board, for every role: the logo goes to `/`, which shows a manager's own board (no more redirect to My team for a team that is just the manager) and sends an admin who runs no team to `/boards` (no more redirect to the Teams portal). A try at a fluid, larger site-wide font size was reverted at the user's request.
- Reason fields marked required show a red star and keep the submit button disabled until something is typed.
- Cards move by dragging; the detail sheet's only status button is Resume on a blocked task.
- `make dev` follows the database log as well as the API and Vite (`make db-logs`).
- Fixed: the due-date picker did nothing inside a dialog (its panel is portaled to `<body>`, where an open Radix dialog turns pointer events off); arrow keys now work in searchable dropdowns.

**Checked.** `tsc` clean; 41 frontend tests (new: `memberFilter.test.ts`, `auditText.test.ts`); 550 server tests; the bundle suite (5 of 5); Teams and Audit screens, the due-date picker (today and a future day set, a past day disabled) and the dropdown's arrow keys looked at in a browser with demo data (light and dark where noted in the checklist).

**Not done or not verified.** Component tests for the new screens; error boundaries; clicking through every dialog; My team in a browser; Playwright; a server coverage report; the open-task warning when removing a person (needs an endpoint). Plan: `refdocs/checklist.md`.

**Slips to know about.** The two audit-name tests were appended to `test_teams.py` with a shell heredoc, and `.env` was sourced once by a command, both against the project rules. Nothing was printed or written to `.env`.

## 17 Oct 2026 (earlier): the tasks backend, one `.env`, no demo passwords

**Summary.** The server now has the whole board: tasks, their timeline and comments, the board query and the team report, on top of the identity feature. Setup moved to one `.env`, with a dev stack and a production stack, and the demo passwords were removed. The frontend now signs in and reads boards on the real API (the mock is being removed). Git is initialised with its remote but nothing is committed, so there are no commit ids to list yet.

**What changed**
- **Tasks backend (`server/tasks/`, see its README).** Tables `tasks` and `task_activity` (migration `0002_tasks.py`, models in `server/models/tasks.py`). Permission rules and the allowed moves in `server/security/authorization.py`; calculated facts (overdue, due soon, needs a new owner, needs attention) in `tasks/rules.py`; five commands in `services/commands.py`; the board, task and timeline queries in `services/queries.py`; the report in `services/report.py`.
- **Endpoints (all under `/api`).** `GET /board`, `POST /tasks`, `GET / PATCH / DELETE /tasks/{id}`, `POST /tasks/{id}/status`, `POST /tasks/{id}/comments`, `GET /reports/team`. Files and rules: `server/tasks/README.md`.
- **Done cards stay on the board**, newest closed first: the server, the mock, the board UI and `plan/PLAN.md` agree. The stale-Done helpers were removed.
- **Adding a member needs no reason**: server rule, mock handler, the dialog (`reasonOptional`), docs and one test.
- **Setup.** `Makefile` loads `.env` for host targets and builds `DATABASE_URL`; new targets `dev` (database, migrations, people, API with `DEV_AUTH=true`, Vite), `dev-down`, `prod-up`, `prod-load-people`, `prod-down`, `prod-logs`. `docker-compose.dev.yml` is the local database, `docker-compose.yml` the production stack (database with no published port, API container with a healthcheck, migrations on start, `DEV_AUTH` off), `Dockerfile.api` and `.dockerignore` build the image from `server/` only. `.env.example` was rewritten in sections.
- **People.** `seed/load_db.py` reads `people.json` as well as the Slack extract; `PEOPLE_FILE` picks the file or folder; production mounts the file into a one-off container, never into the image.
- **Demo sign-in.** The email/password form, `useLogin`, `services/auth.login`, the mock `/auth/login`, `SEED_*_PASS` and the New Hire user are gone; the login page is one "Continue with Google" button. In development it opens the server's account list (`GET /dev/accounts`); a production build goes to Google.
- **Tests and the runner.** `make test` runs every suite (frontend and server) through `scripts/test_all.py`: each test prints its name, PASSED or FAILED and its progress percentage, then a table gives the percentage that passed per suite and overall; the exit code is 1 on any failure or if a suite cannot run. `make client-test` and `make server-test` use the same runner for one suite. The frontend uses `client/vitest.reporter.ts`. New server tests cover the gaps found in an audit: `test_task_access.py` (29), `test_task_validation.py` (76), `test_task_side_effects.py` (37, before-and-after database snapshots), report edge cases (+5) and the dev account list (4).
- **Server settings.** A plain `postgresql://` database URL now gets the installed `psycopg` driver (`core/config.py`); a `.env` URL without a driver made the server look for `psycopg2`.
- **Demo data in the real database (decided with the user: no mock, "server wise").** `make dev` now runs `make db-demo` (`seed/demo_db.py`): Admin, Manager 1 and Manager 2 can sign in; teams NPI and Validation (made through the real services, so the audit log fills in), six fake team members, one of whom has left, and 14 back-dated tasks in every state. It is idempotent, `make db-demo-remove` / `db-demo-reset` take it out or reload it, `make dev-down` keeps it (it lives in the volume) and `down -v` wipes the whole dev database. Dev only: it refuses unless `DEV_AUTH` is on and is not in the production image. The directory load (`make db-seed`) now skips accounts whose Slack id starts `DEMO-`. 16 tests in `test_demo_seed.py`.
- **Google sign-in (`server/auth/`, see its README).** `GET /auth/google`, `/auth/google/callback`, `/auth/google/exchange?code=`; signed session tokens (standard library only), one-time codes in a new `login_codes` table (migration 0003), `get_current_person` accepts `Authorization: Bearer`. Settings (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SECRET_KEY`, `TOKEN_TTL_SECONDS`) are in their own section of `.env.example` and passed to the prod container. 70 tests with Google faked. Found while trying it in the browser: React's development mode ran the login page's effect twice, so the one-time code was traded twice, the first trade saved the session and the second failed and showed "Google authentication failed" (fixed with a ref guard in `LoginPage.tsx`; verified with a real one-time code). The server now logs why Google refused a code. Also: dev sign-ins no longer store a fake token, the dev account list has a "Sign in with real Google" row, and the login brand panel was reworked: one block pushed to the bottom (the "Work Board" label, then the headline, the description and the ATI WORKBOARD wordmark), the dot grid and the green glows ported from AtiUI's split-login pattern (`login-backdrop.css`, tokens only), and the leftover "Phase 1 preview" line removed. Tests are now isolated from the developer's `.env` (`conftest.py` drops every setting except the database), after `make test` broke once the Google settings were added to `.env`.
- **Git.** `git init -b main` and `origin` set to `https://github.com/VikirthanT/workboard.git`; nothing committed or pushed. `.claude/settings.local.json` was added to `.gitignore`; `.env`, `seed/people.json`, `refdocs/` and the generated seed were already ignored, and no file with a private-looking name is among the 204 untracked files.

**What you will see.** `make dev` starts everything and the UI still shows the mock data; sign in with "Continue with Google" and pick Admin, Manager 1 to 3, or the two refused accounts. The Done column keeps every finished card, newest first. `GET /api/board` with `X-Dev-User-Email: <a manager>` returns that team's board.

**How it was checked**
- All tests through `make test` on the user's own `.env` and database: 473 passed (38 frontend, 435 server), then 451 server tests after the demo load was added. Earlier, through the new runner against a throwaway Postgres: 476 passed, 0 failed (41 frontend, 435 server; the server count was 210 before this work), against a throwaway Postgres with a random password, because the user's own `.env` still pointed at the wrong database port. The runner's failure paths were also tried: a deliberately wrong assertion shows `FAILED` with its message, 97.6% and exit 1 (reverted), and a dead or missing `DATABASE_URL` exits 1. `alembic check`: no drift.
- The real UI against a throwaway live stack (API, Vite, Postgres): the single Google button, the account list, signing in as a manager (board with the live review count and server-computed overdue), the refused plain member's message, in light and dark.
- Client: `make typecheck` clean, `make test` 29 passed; the AtiUI token grep prints only the existing `text-[clamp(...)]` in `LoginPage.tsx`.
- Production stack: built and started in a throwaway compose project; the API became healthy, a two-person file loaded through the one-off container (1 admin made), the image holds no loader or people file, and the container sees only `DATABASE_URL`, `DEV_AUTH` and `ALLOWED_EMAIL_DOMAIN`. Then removed.
- `make db-seed` with a missing file or an empty folder prints the note and exits 0.

**Not done or not verified**
- `make server-test`, `make dev` and `make prod-up` were not run through `make` against the user's own `.env`.
- The login page and the reason-optional dialog were not looked at in a browser, light and dark.
- The frontend does not use the real API yet. Wire differences to map: `name` here vs `display_name` in the mock, a bad assignee is 422 here and 403 in the mock, and the header "needs review" count has no endpoint (the board query returns the cards).
- Google sign-in is not built (Phase 1, last); the Slack bot and the weekly Slack directory pull are Phase 2. The "No team yet" page has no demo account now.
- Task `PATCH` ignores an explicit `assignee_id: null` (a task cannot become unassigned); the report and "today" use the server's time zone.
- No frontend tests for the new server rules; no Playwright specs.

## 16 Oct 2026: suggestions and the weekly handover moved out of this branch

**Summary.** At the user's request everything about standup suggestions and the weekly handover was taken out of the project and kept in a snapshot for a later branch. Nothing is committed (the folder is not a git repository in this session) and nothing was pushed.

**What changed**
- A full copy of the project as it was (minus `.env`, `refdocs/`, `deliverables/`, `seed/people.json`, the generated seed) and the three extraction test scripts were copied to `workboard-suggestions-snapshot` next to the project before anything was removed.
- Deleted (with `rm`, because the editor tools cannot delete; the user authorised these exact paths): `client/src/features/suggestions/`, `client/src/services/suggestions.ts`, `plan/Handover weekly discussion.md`.
- Removed from the app: the Suggestions route, menu entries and header badge; suggestion types, wire types and mappers; task `origin`, source quote and "From standup" badges; the suggestion rules and their tests in `permissions.ts` / `permissions.test.ts`; the mock suggestion and submission stores, routes, purge and wire mappers; `pending_suggestion_count` and `counts.suggestions`. Mock storage key bumped to `workboard-mock-db-v4`, so saved demo data resets once.
- Seed: `seed/seed.py` no longer builds submissions or suggestions, and tasks carry no origin or source fields.
- Docs and config: `CLAUDE.md`, `plan/PLAN.md`, `client/ARCHITECTURE.md`, feature READMEs rewritten without suggestions; the `GROQ_*` and `STANDUP_DB_URL` placeholders removed from `.env.example`.

**How it was checked.** See the verification notes at the end of this entry in the final report; the stale generated seed JSON may still carry old keys until `make seed` is run with the user's passwords.

**Not done / not verified.** The seed was not regenerated (no `SEED_*_PASS` in the environment and `.env` was not opened). Older entries below describe the feature as it was; they are history.

## 16 Oct 2026 (earlier): suggestion lifecycle (due default, late flag, expiry, restore)

**Summary.** Suggestions now follow the confirmed lifecycle: a stated due date is used, otherwise the Friday of the standup's week is the default and is shown as such; suggestions from late replies are flagged; pending ones are removed after 3 days; rejected ones are kept 3 days and can be restored. Nothing is committed.

**What changed**
- Rules in `client/src/app/domain/permissions.ts`: `SUGGESTION_TTL_DAYS = 3`, `REJECTED_KEEP_DAYS = 3`, `suggestionExpiresAt`, `isSuggestionRemoved`, `daysLeft`, `canRestoreSuggestion`, `defaultSuggestionDue`, `suggestionDue`, `dueSourceAfterEdit`.
- Types, wire shapes and mappers (`app/types/types.ts`, `services/backendTypes.ts`, `services/mappers.ts`): `dueSource`, `fromLateReply`, `expiresAt`, `daysLeft`, `actions.canRestore`; submissions carry `isLateReply`.
- Mock API (`mocks/handlers.ts`, `wire.ts`, `db.ts`): `purgeSuggestions` runs before every request; new `POST /suggestions/:id/restore`; editing the due date flips `dueSource`. Storage key bumped to `workboard-mock-db-v3`, so saved demo data resets once.
- Seed (`seed/seed.py`): submissions carry source and late flag; suggestions have their own created age; a stated-date suggestion, a late-reply one, a rejected one 1 day old (restorable) and one 4 days old (purged on first request).
- UI (`features/suggestions`): "Due Fri 16 Oct, default" vs a plain stated date, "Late reply" badge, "Expires in N days", "N days left to restore" and a Restore button; `app/lib/format.ts` `formatDayWithWeekday`.
- Docs: `CLAUDE.md`, `plan/PLAN.md`, `features/suggestions/README.md`, `.env.example` (`STANDUP_DB_URL` placeholder). The plan now lives in `plan/` and the stale `refdocs/plan/PLAN.md` references were fixed.

**What you will see.** As `manager1@`: 6 pending NPI suggestions with countdowns (one "Expires in 1 day"), one "Late reply", muted "default" due dates, one stated date; the Rejected tab holds one suggestion with "2 days left to restore" (the 4-day-old one is already gone); Restore moves it to Pending with "Expires in 3 days". As `admin@` on NPI: no Edit, Approve, Reject or Restore.

**How it was checked (all run)**
- `make typecheck`: clean. `make test`: 2 files, 45 tests passed (new: expiry at exactly 3 days, removal at the boundary, restore window and who may restore, fresh expiry after restore, default Friday from a Monday, a stated date overriding the default, due edit flipping the source).
- AtiUI token grep: only the existing `text-[clamp(...)]` in `LoginPage.tsx`.
- Browser (Chrome driven by a script, dev server on a spare port): countdowns, Late reply flag and its tooltip, default vs stated due, the purged rejected suggestion absent, Restore moving the card to Pending with "Expires in 3 days", admin on NPI with no action buttons; light and dark for manager Pending and Rejected. No console errors.
- Seed regenerated with throwaway passwords so `.env` was not read; your password hashes differ until you run `make seed` or `make dev`.

**Not done or not verified**
- A late reply for an earlier week gets the Friday of that week as its default due date, which is already past (the seed's late reply shows "Due Fri 9 Oct, default"). Approving it would create an overdue task; the 3-day expiry limits how long that stays possible.
- The create-team, set-manager and report dialogs, and the admin read-only detail panel in dark mode, were not looked at; the Edit dialog was opened but the due-date edit flow was not completed in a browser (the source flip is unit-tested only).
- No handler-level tests: the mock handlers need the generated seed, so the purge and restore handlers are exercised through the browser only.
- Nothing committed; this folder is not a git repository in this session.

## 16 Oct 2026: admins read every team's Suggestions, read-only

**Summary.** An admin can open any team's Suggestions inbox. The default is the admin's own team (full actions, as a manager); other teams are read-only. Nothing is committed.

**What changed**
- Rule: `canViewSuggestion` in `app/domain/permissions.ts`; review and approval stay manager-of-that-team only. Two new tests (35 in total).
- Mock API: `GET /suggestions` takes `team` (same resolution as the board); edit / approve / reject return 403 unless the viewer runs the team; the team list carries `pending_suggestion_count`.
- UI: `features/suggestions/SuggestionsView.tsx` (admin team dropdown, own team first marked "(yours)", "Read-only view of <team>" line), `SuggestionCard.tsx` hides the buttons when no action is allowed, "Suggestions" entry in the admin's avatar menu (`AppShell.tsx`).

**How it was checked.** `make typecheck` and `make test` (35 tests) pass; token grep prints only the known `LoginPage.tsx` clamp. Not looked at in a browser yet (see below).

## 16 Oct 2026 (later): admin read-only team boards, board opens on all tasks

**Summary.** Admins can now read every team's board, strictly read-only, and the board opens on all tasks with "Needs attention" as a tick. Nothing is committed. `make typecheck`, `make test` (33 tests) and the token grep were run; the only grep hit is the old `text-[clamp(...)]` in `LoginPage.tsx`.

**What changed**
- Rules (`app/domain/permissions.ts`): `canViewTeam` / `canView` read (admin any team); `canAct` / `isTeamManager` act (own team only), used by edit, delete, reassign, comment, transitions and suggestion review; `resolveBoardTeam` decides which team a request means (manager: own only; admin: any, default the team they run).
- Mock API (`mocks/handlers.ts`, `wire.ts`): `GET /board` and `/reports/team` take `team`; the board returns `team`, `read_only` and `attention_count`; `actions` come back empty for an admin on a team they do not run; admins get 404 on suggestion endpoints; `GET /teams` carries `open_task_count`.
- UI (`features/board`): `/boards` route and "Team boards" menu entry for admins, team dropdown, "Read-only view of <team>" line, no New task, no drag (`KanbanBoard readOnly`), no detail footer or comment box (`TaskDetailSheet readOnly`).
- Separate change, same files: **the board now opens on all tasks**; "Needs attention" with its count narrows the cards (`?attention=1` only when on; the old `?view=all` and "Show all tasks" are gone).
- Tests: `permissions.test.ts` 25 to 33 (admin reads all, acts on none, own-team exception, manager refused other teams, `resolveBoardTeam`).
- Docs: `CLAUDE.md`, `PLAN.md`, `client/ARCHITECTURE.md`, board and admin READMEs.

**Not done or not verified.** The admin does not see suggestions (tasks, comments and timeline only). No handler-level tests: the mock handlers need the generated seed, so the rules are tested through the pure module only.

## 16 Oct 2026

**Summary.** Re-scoped the whole client from the Keka / member model to the managers-only Workboard, and added the standup Suggestions inbox against mock data. Nothing is committed.

**What changed**
- Types and rules: `client/src/app/types/types.ts`, `app/domain/permissions.ts` (team rules, manager-only transitions, suggestion rules), tests in `permissions.test.ts` and `report.test.ts` (25 tests).
- Mock API and seed: `mocks/handlers.ts`, `wire.ts`, `db.ts`; `seed/seed.py` (users, teams, tasks in every status, standup submissions, suggestions pending / approved / rejected); `seed/csv_to_people.py` and `seed/people.json` for the directory.
- Services: new `teams.ts`, `suggestions.ts`; reworked `admin.ts`, `tasks.ts`, `reports.ts`, mappers and wire types.
- Features: new `admin` (Teams portal) and `suggestions`; `team` rebuilt around a shared people panel; `board` simplified (no scopes, indirect toggle, departments, self-created, takeover); `access` removed.
- Docs: `CLAUDE.md`, `client/ARCHITECTURE.md`, a README in each feature folder, `plan/PLAN.md` (the plan now lives in `plan/`, tracked), `.env.example`, `Makefile` (build warning), `.gitignore`.

**Routes.** `/` team board, `/suggestions`, `/team`, `/admin`, `/login`.

**What you will see.** Sign in (mock chooser or "Sign in as…"): `admin@` sees Teams; `manager1@` the NPI board with 4 pending suggestions; `manager2@` Validation; `manager3@` is sent to My team (empty team); `newhire@` sees "You are not on any team yet".

**How it was checked (all run)**
- `make typecheck`: clean. `make test`: 2 files, 25 tests passed.
- AtiUI token grep: one hit, an existing `text-[clamp(...)]` in `features/auth/LoginPage.tsx` that this change did not touch; nothing in the new code.
- Browser (Chrome driven by a script, dev server on a spare port): screenshots of the admin Teams page, manager board, Suggestions, My team, the empty-team redirect and the no-team page in light and dark, no console errors. Interaction checks all passed: approving a suggestion puts it on the board with its source quote; rejecting keeps it off the board; Approve is disabled with no assignee; a manager of another team is not offered as a team's manager; an empty team lands on My team and the board opens once someone is added; no-team message.
- Seed run with throwaway passwords so `.env` was not read; the generated seed's password hashes therefore differ from yours. Run `make seed` (or `make dev`) with your own `.env` to restore them.
- Whether `seed.py` exits clearly when `people.json` is missing: checked.

**Not done / not verified**
- No backend, no standup DB, no LLM; suggestions are fixed mock data. (A copy of the standup backup is now in `refdocs/`, used only as a shape reference.)
- Not every screen state was looked at: dialogs (create team, set manager, add person, edit / reject suggestion, report) were exercised only through the add-person flow; the rest are type-checked, not seen.
- No Playwright specs; the browser checks were ad hoc and are not in the repo.
- Real Google OAuth and Slack are not built.
- Nothing committed; this folder is not a git repository in this session, so `git log` checks could not be run.
