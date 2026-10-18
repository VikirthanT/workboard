# Work Board client: architecture

Follows `frontend-architecture-template.md` (React + Vite + React Router + React Query + axios). This document says what the app actually looks like today and where it deviates.

**Stage:** all five growth steps are in use except `shared/`, which is deliberately empty until a third feature needs something. (The `team` panel, reason dialog and status dropdown are used by `team` and `admin`: two consumers, so they stay in `team` and `admin` imports them through its barrel.)

**Model:** managers only. A *user* signs in (admin or manager); a *person* is in the people directory and is only an assignee. One team has one manager, a manager runs one team, a person is on at most one team, a team has one board.

```
client/src/
├── app/
│   ├── App.tsx             Route tree (guard lives in AppShell)
│   ├── components/         AppShell, ui/* (AtiUI copies + sheet.tsx)
│   ├── constants/          queryKeys.ts
│   ├── domain/             dates.ts, report.ts  (pure helpers; permission rules live on the server)
│   ├── lib/                utils.ts (cn), theme.tsx, format.ts
│   └── types/types.ts      Frontend types
├── features/               each has a README.md (endpoints + folder map)
│   ├── auth/               LoginPage, DevAccountChooser (dev builds only), hooks/ (Google exchange, dev sign-in, sign out)
│   ├── board/              BoardView, components/ (Kanban, card, detail sheet, dialogs, report), hooks/
│   ├── team/               TeamView, TeamMembersPanel, TeamSection, filters, add / remove dialogs, reason dialog, NoTeamPage, hooks/
│   └── admin/              TeamsView (Teams portal: Teams, Admins, Audit log tabs), create / delete team, manager and admin dialogs, hooks/
├── hooks/                  useCurrentUser (global)
├── shared/                 empty
├── services/               api.ts barrel, axiosInstance.ts, backendTypes.ts, mappers.ts, auth / tasks / teams / admin / reports .ts, session.ts
└── styles/                 AtiUI tokens (globals.css) + fonts
```

## Data flow

View -> feature hook (`useQuery` / `useMutation`) -> `services/api` -> `apiClient` -> response in `backendTypes` shape (snake_case) -> mapper in `services/mappers.ts` -> frontend type (camelCase) -> React Query cache -> view. Task mutations invalidate `BOARD_KEY`, `TASK_KEY` and `ME_KEY` (header counts); team and admin mutations invalidate `TEAMS_KEY`, `UNASSIGNED_KEY`, `AUDIT_KEY`, `USERS_KEY` plus the board and `ME_KEY`. All keys come from `app/constants/queryKeys.ts`.

401 is handled once in `services/axiosInstance.ts`: it clears the session and dispatches `workboard:unauthorized`; `AppShell` listens and redirects to `/login`.

## Routing

```
/login                public
/                     team board   (home for everyone, always a Kanban board; no team: "No team yet" page; an admin who runs no team: redirect to /boards)
/boards               Any team's board, read-only (admin; `?team=<id>`, defaults to the admin's own team, else the first team with open tasks; others go to /)
/team                 My team: the people a manager assigns work to (manager)
/admin                Teams portal (admin; the view itself shows "Admins only" to anyone else)
```

All sit under the AppShell guard. Board state (team for admins, `attention=1` when the needs-attention tick is on, person, filters, open task) lives in the URL query string (`useBoardParams`), so the header badge deep-links (`/?filter=needs_review`), a link can open a task (`/?task=<id>`), and a refresh keeps the view.

## Deviations from the template

| Deviation | Why |
|---|---|
| Rules live on the server | The permission and transition rules are in `server/security/authorization.py` only. The UI never re-implements a rule; it reads the `actions` each task comes back with (and `read_only` on a board). The in-browser mock and the client's `permissions.ts` were removed on 17 Oct. |
| Dev-only code behind `import.meta.env.DEV` | The dev account chooser, "Sign in as…" and the `X-Dev-User-Email` header are compiled out of a production build; the `bundle` suite in `make test` fails if any of it ships. |
| `app/lib/` | AtiUI's `cn()` and theme code. The copied components import `../../lib/utils`. |
| `app/components/ui/sheet.tsx` | AtiUI has no drawer yet. Candidate to upstream. |
| Two local edits to AtiUI copies | `Select` and `DatePicker` panels raised to `z-[300]` so they open above dialogs/sheets (AtiUI's `z-50` renders them behind the scrim). Upstream these. |
| `admin` reuses `team` | The Teams portal manages any team's people with the same `TeamSection`, filters and dialogs the manager uses for their own (the admin adds role and admin controls), imported through the `features/team` barrel. |
| Cross-feature imports | `board` and `team` use `NoTeamPage` from `features/team`; `admin` uses `features/team`. All go through a barrel, as the template allows. |

## Error boundaries

`app/components/ErrorBoundary.tsx` shows "Something went wrong" and a Reload button when a child throws while rendering, so one failing part does not blank the page. A `label` names the panel ("The audit log could not be shown"); `resetKey` clears the error when it changes. It does not catch failed network calls: the screens show those themselves. Where it is used:

| Level | Where | What it covers |
|---|---|---|
| Page | `app/components/AppShell.tsx:105` | Every routed page; the header stays; `resetKey` is the path, so another page tries again |
| Panel | `features/board/BoardView.tsx:215` | The Kanban board ("The board") |
| Panel | `features/team/TeamView.tsx:19` | My team's people list ("The team list") |
| Panel | `features/admin/TeamsView.tsx:76` | Teams tab ("The teams list") |
| Panel | `features/admin/TeamsView.tsx:108` | Admins tab ("The admins list") |
| Panel | `features/admin/TeamsView.tsx:110` | Audit log tab ("The audit log") |

Tests: `app/components/ErrorBoundary.test.tsx`. Update this table when a boundary is added or moved.

## Auth

Google OAuth contract (same as Mdm Duro): `/login?code=...` -> `GET /auth/google/exchange` -> `{token, email, name}`; `/login?error=<code>` for failures. Only onboarded users sign in. In development the login page lists the server's dev accounts instead (or goes to real Google). There is no email/password sign-in.

## Tests

`make client-test` (vitest, 41 tests) covers the pure code: the wire-to-app mappers and the server's wire contract (`services/mappers.test.ts`), error codes (`errors.test.ts`), the report maths (`app/domain/report.test.ts`), the people search and role filter (`features/team/memberFilter.test.ts`) and the audit sentences (`features/admin/auditText.test.ts`). The permission and transition rules are tested on the server (550 tests). Component tests (Testing Library), service tests that pin each route, and Playwright specs are still to do: see `refdocs/checklist.md`. `make test` also builds the production bundle and checks no dev-only sign-in code is in it.
