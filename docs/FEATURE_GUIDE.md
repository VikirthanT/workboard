
# Work Board: feature guide

One page to explain the Work Board to stakeholders (Part 1) and to engineers (Part 2). Each feature's own README (`server/<feature>/README.md`) is the detailed endpoint reference; this guide ties them together. Status words are literal: *built* means in the repo and covered by tests, *not tried* means built but never run against the real outside service.

---

# Part 1: For stakeholders

## What it is

An internal task board for ATI Motors Engineering. The eight Engineering managers (the NPI team first, as a sandbox) create and assign tasks to their own team and move them across a board. **Team members never log in**: they get their tasks in Slack and update them there. Admins set up teams and can read every board.

## Who does what

| Person | Signs in? | What they can do |
| --- | --- | --- |
| Manager | Yes (Google, `@atimotors.com`) | Runs one team: creates, edits, moves, reassigns and deletes tasks; adds and removes their team's people; reads the team report; reviews standup suggestions |
| Admin | Yes | Creates and deletes teams, picks managers, adds and removes anyone on any team, makes other admins; reads every team's board (read-only) and may comment on any task; reads the audit log |
| Team member | No | Receives tasks as a Slack DM card; moves a task up to Review; comments; sees their open tasks on the bot's Home tab |

One team has one manager, a manager runs one team, a person is on at most one team. Someone who signs in with no team sees "You are not on any team yet, ask an admin".

## The features

| Feature | What a stakeholder sees | Status |
| --- | --- | --- |
| Google sign-in | One "Continue with Google" button, company accounts only, only managers and admins get in | Built; live on the production server over HTTPS (reported by the team) |
| Kanban board | Five columns (To Do, In Progress, Blocked, Review, Done); drag cards; one Filters menu with "Needs attention" (overdue, blocked, in Review, needing a new owner), "Needs my review", overdue, blocked and due this week, each with its count; a search box; overdue cards say "Overdue by N days" | Built |
| Tasks | Title, description, priority (the card colour), project, stage, start and due date, assignee; every change and comment on a timeline that cannot be edited | Built |
| Rules that keep the data honest | A due date cannot be in the past; blocking, moving back, sending back and reopening need a reason; any move to Done needs remarks; a Done task is locked until reopened; only To Do and In Progress tasks can be deleted | Built, enforced on the server |
| Bulk upload | Download an Excel template, fill it in, preview, confirm: all rows are created or none | Built |
| Team report | Per person and in total, for a chosen period; CSV and PDF export; an all-teams report | Built |
| My team / Teams portal | Managers manage their people; admins manage teams, managers, admins; every change is audited with a reason | Built |
| Audit log | Append-only record (the database refuses edits) of team, membership, admin, sign-in, task delete and reassign changes | Built |
| Standup suggestions | The team's standup channel is read, a language model proposes tasks, the manager edits, rejects or adds them; nothing reaches the board without the manager. Synced automatically at the times set in `STANDUP_SYNC_SCHEDULE` (the `scheduler` service); a person with no post reads "Standup not found". An admin can open any team's suggestions read-only and press Sync to check the connection | Built, reads another team's standup database read-only |
| People from Slack | Who exists comes from the Slack workspace, not a file: loaded once on start (which also makes the first admin from `BOOTSTRAP_ADMIN_EMAILS`), refreshed every week (`DIRECTORY_SYNC_SCHEDULE`, for example Sunday night) and when an admin presses "Sync people from Slack" in the Teams portal. People who left are marked inactive (their open tasks then need a new owner), never deleted; admins and everyone's team and role are untouched; a run that would deactivate a large share is refused; every run is in the audit log | Built; not tried against a real workspace here |
| Pull from Slack | A button on the team page lists everyone in the team's Slack channel who is in the directory; the manager (own team) or an admin (any team) ticks who joins and confirms. The dialog says when the channel is not set, cannot be found, or the bot is not in it | Built |
| Slack bot | Assignee gets a DM card with status dropdown and Comment button; manager and assignee comments and every status move appear in the card's thread, **with a teal bar for the manager and a grey bar for the assignee**; a Home tab lists open tasks with created date and time. **Reassigning a task** gives the new assignee their own card with the latest 10 earlier comments and moves under it, closes the old assignee's card ("Reassigned to …", no buttons) and redraws both Home tabs | Built, not tried against a real workspace |
| Slack channel announcement | After a bulk upload or a standup batch: one line per person (`@name - N tasks`) and a PDF with the details | Built |
| Dark and light themes | Follows the AtiUI design system | Built |

## How a task travels

1. The manager creates a task (or uploads a sheet, or adds a standup suggestion) and picks the assignee.
2. The assignee gets a DM card in Slack. For bulk uploads and standup batches the team channel also gets a short post and a PDF.
3. The assignee moves it to In Progress, Blocked (reason needed) or Review. Each move appears in the card's thread and on the board's timeline.
4. The manager reviews, and moves it to Done with remarks, or sends it back with a reason.
5. A few days after Done, the Slack thread is removed; the board keeps the task and its timeline.

## What is not done yet

Confirming the Slack bot against a real workspace and recording the real-Google sign-in check in the repo's docs (HTTPS and Phase 1 are live on the production server); the "due within 2 days" Slack alert; the weekly Slack directory pull; the security audit.

---

# Part 2: For engineers

## Shape of the system

```
 browser ──HTTPS──► [ TLS layer (on the server) ] ──HTTP──► [ nginx :80 ] ──► [ API (FastAPI) ] ──► [ Postgres 16 ]
                                                           │ serves the React build            ▲
 Slack ◄──wss (Socket Mode, we dial out)── [ Slack listener ]──────────────────────────────────┤ same code, same database
 Slack ◄──HTTPS slack.com/api── API and listener (bot token)                                    │
 Google ◄──HTTPS── API (sign-in code exchange, key fetch)        [ standup scheduler ] ─────────┘
```

Features are folders: `server/identity`, `tasks`, `auth`, `standups`, `slack`; each has `routers/` (HTTP), `services/` (logic) and a README. Shared code: `server/security/` (authentication, authorization, rate limits), `server/core/` (settings, errors), `server/models/`, `server/database/`. Permissions live only in `server/security/authorization.py`; the UI reads the `actions` the API returns.

## Command-query separation

A **command** checks the rules, writes, commits once and returns nothing (a command that creates something takes the new id from the caller). A **query** reads and changes nothing. A router runs the command, then a query to build the response. So every write endpoint below is "command, then query", and every GET is a query only.

## Endpoints by feature

All under `/api`. Errors are always `{"detail": {"code", "message"}}`. Full tables with request bodies and error codes are in each README.

### auth (`server/auth/README.md`)

| Endpoint | Kind | Service function | What it does |
| --- | --- | --- | --- |
| `GET /auth/google` | command | `google.authorize_url`, `tokens.sign` | Sets a signed HttpOnly cookie with random `state` and `nonce`, redirects to Google |
| `GET /auth/google/callback` | command | `google.exchange_code`, `verify_signature`, `verified_email`, `require_company_domain`, `person_for_email`, `login_codes.issue`, `login_audit.record_login` | Checks `state` against the cookie, trades Google's code for the ID token, proves its signature, issues a one-time code, redirects to `/login?code=` (or `?error=<code>`) |
| `GET /auth/google/exchange?code=` | command | `login_codes.consume`, `tokens.sign` | Spends the one-time code (60 s, once), returns `{token, email, name}` with `Cache-Control: no-store` |
| `POST /auth/logout` | command | `sessions.end_sessions` | Bumps the person's `session_version`, so every token already issued stops working |

How it works: the session token is an HMAC-signed token (`SECRET_KEY`, at least 32 characters) carrying the person and `session_version`, valid `TOKEN_TTL_SECONDS` (default 8 hours); `get_current_person` verifies it on every call. Google's ID token is verified RS256-only against Google's published keys, with issuer, audience, expiry, nonce and verified-email checks; the domain is matched as a whole suffix (`@atimotors.com`, so `x@atimotors.com.evil.com` fails). Refused and successful sign-ins are audited. Per-email limit: 10 attempts in 10 minutes (`too_many_attempts`).

### identity (`server/identity/README.md`)

| Endpoint | Kind | What it does |
| --- | --- | --- |
| `GET /me` | query | The signed-in person with team name |
| `GET /people?unassigned=&admins=&q=&limit=&offset=` | query | Paged directory search for the pickers |
| `GET /audit-log?limit=&offset=` | query | Paged audit entries, newest first (admin) |
| `GET /teams`, `GET /teams/{id}/members` | query | Teams (admin: all; manager: own); members with `open_task_count` |
| `POST /teams` | command | Create a team and make its first person the manager, one transaction (admin) |
| `PATCH /teams/{id}/manager` | command | Replace the manager; the old one stays as a member (admin) |
| `PATCH /teams/{id}/standup-channel` | command | Set or clear the standup channel (admin or that manager) |
| `DELETE /teams/{id}` | command | Erase a team for good; body repeats its name and a reason (admin) |
| `GET /teams/{id}/channel-members` | query | Who is in the team's Slack channel and in the directory, with what adding each would do (admin or that manager); says why when the channel is not set, not found, or the bot is not in it |
| `POST /teams/{id}/members/bulk` | command | Add the ticked people together, all or none, one audit row each (admin or that manager) |
| `POST /teams/{id}/members`, `DELETE /teams/{id}/members/{person_id}` | command | Add a person with no team / remove one (admin or that manager); the manager cannot be removed |
| `POST /people/sync` | command | Refresh the people from the Slack workspace now (admin, 3 a minute); audited under the admin's name; refused if it would deactivate a large share |
| `PATCH /people/{id}/admin` | command | Make or revoke admin; the last active admin cannot be revoked |
| `GET /dev/accounts` | query | Dev sign-in list; 404 unless `DEV_AUTH` is on |
| `GET /health` | query | Liveness, no sign-in |

How it works: services take the actor, check the rule, write the change and an `access_audit_log` row in the same transaction, then commit once. Team rows are locked (`FOR UPDATE`) so two admins cannot interleave. The audit table is append-only through a database trigger.

### tasks (`server/tasks/README.md`)

| Endpoint | Kind | Service function | What it does |
| --- | --- | --- | --- |
| `GET /board?team=&person=&filter=&attention=&limit=&show=` | query | `queries.get_board` | Cards with `actions`, counts, orphans; admin gets `read_only: true` |
| `GET /tasks/{id}` | query | `queries.get_task_detail` | Task and timeline |
| `GET /reports/team`, `GET /reports/all-teams` | query | `report.get_team_report`, `get_all_teams_report` | Counts per person and in total for a period |
| `GET /tasks/import/template` | query | `import_template` | Fresh `.xlsx` with dropdowns |
| `POST /tasks` | command | `commands.create_task` | Create on the manager's own team |
| `PATCH /tasks/{id}` | command | `commands.update_task` | Only fields sent; one timeline entry per real change; reassign is audited |
| `DELETE /tasks/{id}` | command | `commands.delete_task` | Only To Do or In Progress; snapshot to the audit log first |
| `POST /tasks/{id}/status` | command | `commands.move_task` | Body `{to, note?, completed_on?}`; reason or remarks as the rules require |
| `POST /tasks/{id}/comments` | command | `commands.add_comment` | Manager or any admin, not on a Done task |
| `POST /tasks/import` | command | `commands.import_tasks` | Parses the sheet, all rows or none; `?preview=true` saves nothing |

Not HTTP, but commands the Slack side uses: `move_task_as_assignee` (up to Review) and `add_comment_as_assignee`, which run the same rules and write the same timeline, marked `source = slack`. After the reply is sent, the routers call `slack.services.announce.flush_team` so a slow Slack never delays the board.

### standups (`server/standups/README.md`)

| Endpoint | Kind | What it does |
| --- | --- | --- |
| `GET /standups/channels` | query | Channels in the standup database, read live (admin or manager) |
| `GET /standups/channels/{channel_id}` | query | The name of a channel id: the standup database first, then Slack (admin or manager) |
| `GET /teams/{id}/suggestions` | query | Each person's last standup and their suggestions |
| `POST /teams/{id}/suggestions/sync` | command | Reads the channel (this week's standups only, from this week's Monday) and records "Last sync"; no model call, so it is quick. The team's manager, or any admin (to check the connection) |
| `POST /teams/{id}/suggestions/suggest?person_id=` | command | Asks the language model for tasks from this week's posts, for the whole team or one person, and stores them as suggestions; runs inside the request. The team's manager, or any admin; the rest stays with the manager |
| `PATCH /suggestions/{id}`, `POST .../reject`, `POST .../restore` | command | Edit, reject, bring back (restorable for 3 days) |
| `POST /teams/{id}/suggestions/add` | command | Create a task from each chosen suggestion, all or nothing. A due date is compulsory: one a suggestion lacks (or the manager changes) is sent in `due_dates`; without it the server answers 422 `due_date_required` |

The scheduler (`python -m standups.scheduler`, times from `STANDUP_SYNC_SCHEDULE`) runs the same sync and suggest steps with no actor. Neither creates or deletes tasks, only replaces pending and rejected suggestions. The standup database is opened read-only.

### slack (`server/slack/README.md`)

No HTTP endpoints: a Socket Mode listener turns Slack events into service calls (status dropdown, Comment, Details, Home filters, Home opened). Commands: record and flush announcements, send and refresh DM cards, post thread lines, `interactions.move` and `comment`, `home.publish`. Queries: the form and popup builders, the pure `blocks.*` functions. Thread lines carry the side's bar (`MANAGER_BAR` teal, `ASSIGNEE_BAR` grey). The Home row shows the created date and time in Indian time.

## Requests, TLS and HTTPS

| Topic | How it works today |
| --- | --- |
| **TLS to the app** | HTTPS is ended in front of the app on the production server (set up there, Phase 1 is live on prod; reported by the team, the certificate and front layer are not in this repo, so not re-checked here). Inside the repo nginx listens on port 80 only (`nginx/nginx.conf`) and receives plain HTTP from that layer. Google needs an HTTPS redirect address, which this provides. |
| **HSTS** | `Strict-Transport-Security: max-age=31536000` is sent on every response; browsers honour it now that the site is served over HTTPS. |
| **Outbound TLS** | Calls to Google (code exchange, signing keys) and Slack (`slack.com/api`, the Socket Mode WebSocket) are HTTPS/WSS. Database traffic stays on the private Docker network; whether Postgres itself uses TLS is not set up in this repo's compose files (not checked beyond that). |
| **Who is calling** | `Authorization: Bearer <token>` on every call. The dev header `X-Dev-User-Email` works only with `DEV_AUTH=true`; nginx blanks it on `/api/` and answers `/api/dev/...` with 404, and compose forces `DEV_AUTH` off (two locks). |
| **Security headers** | On every response, errors included: nosniff, no framing, referrer policy, HSTS, Permissions-Policy (camera, microphone, location, payment, USB off), and a Content-Security-Policy (self only; the one inline theme script is allowed by hash). |
| **Request size** | 1 MB everywhere; 3 MB on the bulk upload (the API allows a 2 MB file and 500 rows). |
| **Rate limits** | nginx, per visitor address: 600 requests a minute (burst 200) on `/api/`, 30 a minute (burst 15) on `/api/auth/`; over the limit is 429. The API, per login (one signed-in manager or admin; all their browsers and tabs share it): 300 calls a minute for everything; tighter for the costly calls: 6 bulk uploads, **3 standup suggests** (whole team or one person; it runs the model; the scheduled run is not counted), **20 Slack lookups** (a channel's members, a channel's name and the read-only standup sync share it) and **3 people syncs from Slack** (the admin's button; the weekly run is not counted) a minute; per email: 10 sign-in attempts in 10 minutes. Adding people in bulk (the Pull from Slack review's Add) has only the general limit. The in-app counters are per process (two workers, so up to double). |
| **Visitor address** | Read from `X-Forwarded-For` only when it comes from a private address; a visitor cannot choose the address that is counted. Check the access log after deploying. |
| **Logs** | The access log holds the path, never the query string, because the one-time sign-in code travels in `?code=`. |
| **API docs pages** | `/docs`, `/redoc`, `/openapi.json` answer 404 through nginx. |
| **Timezone** | The API runs in IST (`TZ=Asia/Kolkata`): "today", due dates, overdue and reports use the Indian date. |

Details and the checks that keep these from being dropped: `docs/DEPLOYMENT.md` and `server/tests/test_deployment_config.py`.

## Checking it

`make server-test` (966 passed, 0 failed on 15 Nov 2026), `make client-test`, `make typecheck`. Slack and Google are faked in the tests.
