# board

The manager's board for their one team: five columns (To Do, In Progress, Blocked, Review, Done), task detail with comments and an append-only timeline, create / edit, reasons for Blocked / send back / reopen / move back, remarks to close, and a team report. With no team the page shows `NoTeamPage` (from `features/team`); an admin who runs no team is sent on to `/boards`. `/` (the logo) is the home page for every role and is always a Kanban board; there is no redirect to the Teams portal or My team.

The board opens on **all tasks**; "Needs attention" (with its count) is a tick that narrows the cards, and is kept in the URL as `?attention=1` only when on.

**Admin read-only view** (`/boards?team=<id>`, `BoardView adminView`): a team dropdown (every team, "Team (Manager name)"), a "Read-only view of <team>" line, no Add task button, no dragging and no edit actions. An admin can comment on any task that is not Done (the API sends `can_comment: true` for them). The API sends `read_only: true` and the `actions`; the UI only reads them. An admin who runs a team has full actions on that team only and opens that board by default.

**How a card moves:** by dragging. The detail sheet has one status button, Resume, on a blocked task. A Done task cannot be edited (the sheet says so); reopen it first. A due date cannot be in the past (the picker greys those days out and the server refuses them). In the person filter the signed-in manager appears as "Name (You)".

## Endpoints (all real, see `server/tasks/README.md`)

| Method and path | Where it is called | What it does |
|---|---|---|
| `GET /board?team=` | `services/tasks.ts` `getBoard`, `hooks/useBoard.ts` | The team's cards, stats, filter counts, attention count, tasks needing a new owner, `read_only`. `team` is for admins; a manager is refused another team |
| `GET /reports/team?team=` | `services/reports.ts`, `hooks/useTeamReport.ts` | Per-person and total numbers, all time and for a period (same team rule) |
| `POST /tasks` | `createTask`, `TaskFormDialog.tsx` | New manual task |
| `GET /tasks/:id` | `getTask`, `hooks/useBoard.ts` `useTask` | Task and its timeline |
| `PATCH /tasks/:id` | `updateTask` | Edit or reassign |
| `DELETE /tasks/:id` | `deleteTask` | Only while To Do / In Progress |
| `POST /tasks/:id/status` | `moveTask` | Any move the server allows (`transitions` on the task) |
| `POST /tasks/:id/comments` | `addComment` | Comment (source `workboard`; `slack` in Phase 2); the team's manager or any admin |

Rules: `server/security/authorization.py`. The UI reads the `actions` the API returns and never re-implements a rule.

## Folder map

```
board/
├── BoardView.tsx
├── pdf.ts                 Report PDF download
├── components/            KanbanBoard, TaskCard, TaskDetailSheet, TaskFormDialog, ReasonDialog,
│                          FilterMenu, BoardPanels (orphan banner), ReportDialog, ReportVisuals
├── hooks/                 useBoard / useTask, useTaskMutations, useBoardParams (URL state), useTeamReport
└── index.ts
```

**Error boundary.** The board is wrapped in `ErrorBoundary` (`BoardView.tsx:215`, label "The board"): a render error there shows a fallback and the header and the rest of the page keep working. All boundaries: `client/ARCHITECTURE.md`, "Error boundaries".
