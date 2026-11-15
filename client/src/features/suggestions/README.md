# suggestions

Tasks proposed from the team's standup posts, for the manager to review. A sync reads the team's standup channel (set by an admin on the team), asks a language model which tasks are worth tracking, and stores them as suggestions. Nothing is on the board until the manager adds it. The server owns every rule (who may do what, the 3-day keep time, what a task needs); this feature only calls the API and shows what comes back. Server side: `server/standups/README.md`.

Built so far: the data layer (below). The page, the header link and the dialogs are next, from `docs/mockups/suggestions.html`.

## Endpoints used (all real, see `server/standups/README.md`)

| Method and path | Where it is called | What it does |
|---|---|---|
| `GET /api/teams/{id}/suggestions` | `services/standups.ts` `getSuggestions`, `hooks/useSuggestions.ts` `useSuggestions`, `usePendingSuggestionCount` | Each person with their latest standup (three sections) and suggestions |
| `POST /api/teams/{id}/suggestions/sync` | `syncSuggestions`, `useSyncSuggestions` | Read the channel, propose tasks, return the page |
| `POST /api/teams/{id}/suggestions/add` | `addSuggestions`, `useAddSuggestions` | Create a task from each chosen suggestion (all or nothing); also refreshes the board. Every task needs a due date: the Add dialog shows a required date picker per ticked suggestion (its own date, or empty, or one that has passed), Create stays disabled until each has one, and the dates are sent by suggestion id. The server refuses an add without them. |
| `PATCH /api/suggestions/{id}` | `editSuggestion`, `useEditSuggestion` | Change a pending suggestion; only the fields given |
| `POST /api/suggestions/{id}/reject` | `rejectSuggestion`, `useRejectSuggestion` | Reject (restorable for 3 days) |
| `POST /api/suggestions/{id}/restore` | `restoreSuggestion`, `useRestoreSuggestion` | Bring back a rejected one |

The channel picker uses `GET /api/standups/channels` (`getStandupChannels`, `features/admin`): the standup app's own channel list, read live from its database, and refreshed after every sync so a newly added channel appears. A typed channel id shows its name through `GET /api/standups/channels/{id}` (`getChannelName`, `useChannelName`).

Who sees what: a manager sees their own team and can sync, tick, edit, reject, restore and add. An admin picks any team from a dropdown and sees it read-only, but may press Sync (to check the standup connection); the server enforces both (`security/authorization.py`, `can_sync_standups`). A person with no post this week (an earlier week's standup is never read or shown) reads "Standup not found · checked <date>" once a sync has run, "Not synced yet" before.

## Folder map

```
suggestions/
├── hooks/useSuggestions.ts   queries and mutations; query keys come from app/constants/queryKeys.ts
├── pendingCount.ts           how many suggestions wait for review (the header badge)
├── pendingCount.test.ts
└── index.ts                  the barrel other features import from
```

Wire shapes (snake_case) are in `services/backendTypes.ts`, the mapper in `services/mappers.ts` (`mapSuggestionsPage`), the app types in `app/types/types.ts`.
