# tasks

The board: tasks, their timeline and comments, the board query and the team report. Everything is under `/api`.

Rules in one paragraph: a task belongs to one team and is assigned to an active person on that team (the manager counts). Only that team's manager acts on it (create, edit, move, delete); any admin reads every team's board, read-only, and may comment on any task that is not Done. The moves between To Do, In Progress, Blocked, Review and Done are fixed (`security/authorization.py`); blocking, moving back, sending back and reopening need a reason, and every move into Done needs remarks, stored on the timeline entry. A task can be deleted only while To Do or In Progress. Comments are timeline entries of kind `comment`, allowed on any task that is not Done. Done cards stay on the board, the most recently closed on top. Overdue, due soon and "needs a new owner" are calculated, never stored.

## Endpoints

| Method and path | Who | File | What it does |
| --- | --- | --- | --- |
| `GET /api/board?team=&person=&filter=&attention=` | manager (own team), admin (any, read-only) | `routers/board.py` | The team's cards with their `actions`, the person dropdown, `filter_counts`, `attention_count`, `stats` and `orphans`. `filter` is a comma list of `needs_review`, `overdue`, `blocked`, `due_week`; an unknown one is 422. `attention=true` keeps only what needs the manager. An admin with no team of their own must pass `team`. |
| `POST /api/tasks` | the team's manager | `routers/tasks.py` | Create on the caller's own team. Body `{title, description?, priority?, due_at?, assignee_id}`. Returns 201 with the task. |
| `GET /api/tasks/{id}` | manager of that team, any admin | `routers/tasks.py` | The task and its timeline (oldest first, comments included). |
| `PATCH /api/tasks/{id}` | the team's manager | `routers/tasks.py` | Change only the fields sent; `due_at: null` clears the date. One timeline entry per field that really changed; a new assignee is a `reassign` entry and also a `task.reassign` row in the audit log. A due date cannot be set in the past (422 `due_date_past`; keeping an old date or clearing it is fine). A Done task cannot be edited or reassigned (409 `task_done`; reopen it first). |
| `DELETE /api/tasks/{id}` | the team's manager | `routers/tasks.py` | Only while To Do or In Progress. The timeline goes with it, but a `task.delete` row in the append-only audit log first keeps a snapshot (title, status, priority, due date, assignee, and the whole timeline). Returns 204. |
| `POST /api/tasks/{id}/status` | the team's manager | `routers/tasks.py` | Move a card. Body `{to, note?, completed_on?}`; `note` is required when the move needs a reason (remarks for Done). `completed_on` (a date, only with `to: done`) is the day the work really finished, from the task's due date (when that has passed, else no earliest day) up to today; it becomes the closed date and is added to the timeline remark, and the due date is not touched. Errors: 422 `completed_on_invalid`, `completed_on_not_done`. |
| `POST /api/tasks/{id}/comments` | the team's manager, or any admin on any team | `routers/tasks.py` | Add a comment (not on a Done task). Body `{body}`. Returns 201 with the timeline entry. |
| `GET /api/reports/team?from=&to=&team=&person=` | manager (own team), admin (any) | `routers/reports.py` | Per person and in total, for all time and for the period `from` to `to` (dates, `from` not after `to`). |

Every task comes back with `actions` (`can_edit`, `can_delete`, `can_change_assignee`, `can_comment`, `transitions`), so the UI shows only what the server would allow. For an admin looking at a team they do not run, all of them are false or empty and the board says `read_only: true`.

## Errors

Every failure is `{"detail": {"code", "message"}}`; match on `code`.

| Status | Codes |
| --- | --- |
| 400 | `choose_team` (an admin with no team of their own asked for a board without `team`) |
| 401 | `not_authenticated` |
| 403 | `forbidden` (not this team's manager, or not allowed to read it), `no_team` |
| 404 | `task_not_found`, `team_not_found`, `activity_not_found` |
| 409 | `invalid_transition`, `not_deletable`, `task_done` |
| 422 | `reason_required`, `title_required`, `comment_required`, `invalid_assignee`, `unknown_filter`, `invalid_range`, `invalid_input` (text the database cannot store, such as a NUL character). A malformed body, id or date is also 422, in FastAPI's own shape. |

## Folder map

```
server/tasks/
├── routers/
│   ├── __init__.py        assembles the one `router` (board + reports + tasks)
│   ├── board.py           GET /board
│   ├── reports.py         GET /reports/team
│   └── tasks.py           the task endpoints
├── services/
│   ├── lookup.py          get_task, get_task_and_team (404 if missing)
│   ├── activity.py        record one timeline entry (adds the row; the command commits)
│   ├── commands.py        create_task, update_task, delete_task, move_task, add_comment
│   ├── queries.py         resolve_board_team, get_board, get_task, get_task_detail, get_activity
│   └── report.py          report_counts (pure), get_team_report
├── rules.py               overdue, due soon, due this week, needs a new owner, needs attention (pure)
├── schemas.py             request and response models
└── states.py              length limits and timeline field labels
```

Shared code used here, kept outside the feature: `server/models/tasks.py` (`Task`, `TaskActivity`), `server/security/authorization.py` (who may act, the allowed moves), `server/identity/services/lookup.py` (`get_team`, `get_person`), `server/database/`, `server/core/`, `server/migrations/versions/0002_tasks.py`.

## Conventions

- **Command-query separation.** `commands.py` functions check, write, commit once and return nothing; a command that creates something takes the new id from the caller. `queries.py` and `report.py` read and change nothing. A router runs the command, then a query to build the response.
- Permission rules live in `security/authorization.py` and nowhere else: the client has no copy and only reads the `actions` each task comes back with. The calculated facts (overdue, due soon) live in `rules.py`; the client's date helpers in `client/src/app/domain/dates.ts` only format them. Change a rule here with a test.
- Deleting a team writes one `task.delete` snapshot per task (`services/deletion_audit.py`, shared with the single-task delete) plus the team's own `team.delete` row.
- The database enforces what it can: check constraints on status, priority, kind and source; deleting a team deletes its tasks and their timeline; `task_activity` refuses `UPDATE` (a trigger), except that a person leaving may null `actor_id`. `DELETE` is allowed there only so a deleted task or team can take its history with it, so the timeline is edit-proof, not delete-proof.

## Not built yet

- Slack: `accepted_at` on tasks and the comment `source = slack` exist, nothing writes them (Phase 2).
- An open-task count per person (for the "remove from team" warning) and per team (for the admin's team dropdown): no endpoint yet.

Tests: `server/tests/README.md`.
