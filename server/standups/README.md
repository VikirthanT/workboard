# standups

Tasks proposed from the standup notes. The standup app (another team's, SQLite) keeps the notes; we only read them, through a read-only connection set by `STANDUP_DB_URL`. Each team stores which standup channel it uses (`teams.standup_channel_id`, required when an admin creates the team and changed through identity's `PATCH /api/teams/{id}/standup-channel`). A sync reads that channel's posts by that team's people (matched to the standup app's persons by Slack id, then email), asks the language model for the tasks worth tracking, checks the answer, and stores the result as suggestions. Nothing is on a board until the manager adds it.

**Automatic sync.** The `scheduler` service (`python -m standups.scheduler`; `make scheduler-dev` locally) reads every team that has a standup channel at the times in `STANDUP_SYNC_SCHEDULE` (India time, for example `tue 12:00, wed 12:00`: standups are posted on Monday and people load their text on Tuesday, and Wednesday catches late ones). It is the same read as the Sync button, with no signed-in person, and it never creates a task. Empty means never automatically. Each look at the whole team is recorded in `teams.standup_synced_at` even when nothing was found; the Suggestions page shows it as "Last sync", and a person with no post in the last 14 days reads "Standup not found · checked <date, time>" (before the first sync it reads "Not synced yet"). A sync of one person only does not set it. The model comes from `LLM_PROVIDER`, `LLM_MODEL` and `LLM_API_KEY` in `.env` (`anthropic` for Claude).

How a suggestion lives: `pending` until the manager edits, rejects or adds it. A rejected one can be restored for 3 days. Pending and rejected ones are removed 3 days after they last changed (at the next sync), and also as soon as the same person's newer standup is read: a newer standup replaces what their older ones proposed (done before the model reads it, and undone if the model call fails). An approved one is never removed and keeps the link to its task. The page shows the day each person actually posted (`posted_at`, the standup app's `created_at`, stored there in UTC), not the standup's date. A post already read is not read again unless its text changed (`standup_reads` holds a hash of it). Adding is all or nothing: the first task that breaks a task rule stops it and none are created.

## Endpoints

All under `/api`. Every endpoint needs a signed-in person (401 otherwise).

| Method and path | Who | File | What it does |
| --- | --- | --- | --- |
| `GET /api/standups/channels` | admin, manager | `routers/channels.py` | Every channel in the standup database, by name (`slack_channel_id`, `name`), for the channel picker (an admin's, or a manager's for their own team). |
| `GET /api/standups/channels/{channel_id}` | admin, manager | `routers/channels.py` | A query: the name of a channel id (letters and digits, 3 to 32), shown beside the id on the team page. The standup database's own list answers first (no Slack call); an id it does not list is asked of Slack. 404 `channel_not_found`, 409 `bot_not_in_channel`, 501 `slack_not_configured` (neither is set up), 502 `slack_failed`, 422 for a malformed id. |
| `GET /api/teams/{id}/suggestions` | the team's manager; an admin (read only) | `routers/suggestions.py` | Each person on the team, manager first, with the standup they last posted (three sections, or one `message`, or `null`) and their suggestions. Suggestions show for 3 days after they last changed. `last_synced_at` and `standup_channel_id` ride along. |
| `POST /api/teams/{id}/suggestions/sync?person_id=` | the team's manager, or any admin (to check the connection; it only stores suggestions for the manager, edit, reject, restore and add stay with the manager) | `routers/suggestions.py` | Read the channel (last 14 days), propose tasks, return the same page. With `person_id`, only that person's posts, so a manager can go one person at a time (404 `person_not_on_team` for anyone else). Runs the language model, inside the request. |
| `POST /api/teams/{id}/suggestions/add` | the team's manager | `routers/suggestions.py` | Body `{suggestion_ids}`. Create a task from each chosen pending suggestion, assigned to the person it is for; all or nothing. Returns the page. |
| `PATCH /api/suggestions/{id}` | the team's manager | `routers/suggestions.py` | Change a pending suggestion: title, description, priority, person, start or due date (sending a due date makes it the manager's own). Only the fields sent change. |
| `POST /api/suggestions/{id}/reject` | the team's manager | `routers/suggestions.py` | Reject a pending suggestion. |
| `POST /api/suggestions/{id}/restore` | the team's manager | `routers/suggestions.py` | Bring back one rejected in the last 3 days. |

"The team's manager" means the person who runs the team, or an admin acting on a team they run; an admin on another team can only read.

## Errors

Every failure is `{"detail": {"code", "message"}}`; match on `code`.

| Code | Status | When |
| --- | --- | --- |
| `forbidden` | 403 | Not allowed on this team (see the table). |
| `suggestion_not_found` | 404 | The suggestion is gone (including one removed after 3 days). |
| `suggestion_not_pending` | 409 | It was already added or rejected. |
| `not_restorable` | 409 | It is not rejected, or was rejected over 3 days ago. |
| `standup_channel_not_set` | 409 | The team has no standup channel; an admin sets one. |
| `invalid_title`, `invalid_description`, `invalid_priority`, `invalid_assignee` | 422 | An edit broke a rule. |
| `due_date_past` and the other task rules | 422 | Adding: a task rule failed; the message starts with the suggestion's title. |
| `standups_not_configured` | 501 | `STANDUP_DB_URL` is not set (the sync and the channel list need it; the page works without it). |
| `llm_not_configured` | 501 | `LLM_PROVIDER`, the model, or the key is missing; the message names it. |
| `llm_failed` | 502 | The language model could not be reached or its answer was unusable. |

## Folder map

```
standups/
├── schemas.py                 request and response models
├── states.py                  KEEP_DAYS (3), SYNC_DAYS (14)
├── routers/                   channels.py, suggestions.py (assembled into one router in __init__.py)
├── services/
│   ├── channels.py            the channel list and a channel's name (queries; admin or manager)
│   ├── queries.py             the page for a team, one suggestion, last sync time
│   ├── suggestions.py         edit, reject, restore, add to the board, expire (commands)
│   ├── sync.py                read a channel and store suggestions (a command)
│   └── matching.py            which team member posted a submission
├── llm/
│   ├── provider.py            one call to Groq, Claude or an OpenAI-compatible host, from env settings
│   ├── prompt.py              the extraction prompt, its answer schema and its hash
│   └── extract.py             one submission in, checked suggestions out (quote, duplicates, cap of 10)
└── standup_db/reader.py       read-only reader of the standup app's database (channels, submissions)
```

Settings (`core/config.py`, all from the environment): `STANDUP_DB_URL`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`; see `.env.example`. Tables: `task_suggestions`, `standup_reads` (`models/suggestions.py`).
