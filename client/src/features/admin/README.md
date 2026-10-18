# admin

The admin's Teams portal at `/admin`. Every team is a collapsible group with its people; above them a search box and a role filter. On each person: an Admin tick, a Manager / Member dropdown and a dustbin. An "Admins" tab lists everyone with admin access, on a team or not, with "Add admin" (anyone in the directory, reason required) and a dustbin to remove admin access; with one admin left the dustbin is locked. A third tab, "Audit log", lists every change, newest first, fifty at a time (including task deletions and reassignments). Every change asks for a reason and is audited. Admins can also read every team's board, read-only, from "Team boards" in the avatar menu (`/boards`, in `features/board`).

One team has one manager and a manager runs one team. A manager is replaced, never demoted on their own: the manager's row is fixed, and picking Manager on a member's row makes them the manager (the old one stays on the team as a member). The last active admin cannot be revoked (the server refuses and its message shows in the dialog).

## Endpoints used (all real, see `server/identity/README.md`)

| Method and path | Where it is called | What it does |
|---|---|---|
| `GET /api/teams` | `services/teams.ts` `getTeams`, `hooks/useAdmin.ts` `useTeams` (also feeds the board's team dropdown) | Every team, with manager and member count |
| `GET /api/teams/{id}/members` | `getTeamMembers`, `useAllTeamMembers` | The people of each team, for the grouped list |
| `POST /api/teams` | `createTeam`, `CreateTeamDialog.tsx` | Create a team with a first person (becomes manager) and a reason |
| `DELETE /api/teams/{id}` | `deleteTeam`, `DeleteTeamDialog.tsx` | Delete for good: type the name, give a reason |
| `PATCH /api/teams/{id}/manager` | `changeManager`, `ManagerChangeDialog` in `PersonDialogs.tsx` | Make a member the manager |
| `PATCH /api/people/{id}/admin` | `setAdmin`, `AdminToggleDialog` in `PersonDialogs.tsx`, `AddAdminDialog.tsx` | Make or revoke admin |
| `GET /api/people?admins=true` | `getAdmins`, `AdminsPanel.tsx` | Everyone with admin access |
| `GET /api/people?q=` | `searchPeople`, `AddAdminDialog.tsx` | The "Add admin" picker |
| `GET /api/audit-log?limit=&offset=` | `getAudit` in `services/admin.ts`, `AuditLog.tsx` | One page of the audit log, with names |

Add person and the dustbin are the shared ones in `features/team` (`POST` and `DELETE /api/teams/{id}/members`).

## Folder map

```
admin/
├── TeamsView.tsx          The page: header, filters, grouped teams, audit tab, and which dialog is open
├── AdminsPanel.tsx        The Admins tab
├── AddAdminDialog.tsx     Pick anyone in the directory and make them admin
├── AuditLog.tsx           Audit table with Newer / Older paging
├── auditText.ts           describeAudit (one sentence per action), pageRange
├── CreateTeamDialog.tsx   Name + first person + reason
├── DeleteTeamDialog.tsx   Type the team's name + reason
├── PersonDialogs.tsx      ManagerChangeDialog, AdminToggleDialog
├── hooks/                 useTeams, useAllTeamMembers, useAudit, useCreateTeam, useDeleteTeam, useChangeManager, useSetAdmin
├── auditText.test.ts
└── index.ts
```

Imports the grouped list, filters, add and remove dialogs and the reason dialog from `features/team`.

**Error boundaries.** Each tab is wrapped in `ErrorBoundary` in `TeamsView.tsx`: Teams (line 76, "The teams list"), Admins (line 108, "The admins list"), Audit log (line 110, "The audit log"). One failing tab shows a fallback and the others keep working. All boundaries: `client/ARCHITECTURE.md`, "Error boundaries".

## Not built here

- The remove dialog does not warn how many open tasks the person has: no endpoint gives that count yet (see the worklog, step 4).
