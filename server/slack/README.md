# slack

The Slack side of the Work Board: a bot that DMs each assignee their task as a card, lets them move it and comment from Slack, shows their open tasks on the bot's Home tab, and posts a short announcement (with a PDF) in the team's channel when tasks are added in bulk or from standups.

**There are no HTTP endpoints here.** Slack talks to a separate long-running process, the listener, over Socket Mode: the listener dials out to Slack (a secure WebSocket, `wss://`), so no public address, inbound port or certificate of ours is needed for it. Everything the bot sends goes out as HTTPS calls to `slack.com/api` (`client.py`). Both tokens are in `.env` (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, see `docs/SLACK_SETUP.md`). Without them the listener says so and stays idle, and every Slack call is skipped.

Run it with `make slack-dev`; in production it is the `slack` service in `docker-compose.yml`.

## What a person sees

| Where | What | Built in |
| --- | --- | --- |
| DM, Messages tab | One card per task: title, description, `Priority`, `Created`, `Due`, `Status`, a status dropdown and a Comment button (only the moves and comments the server allows). The card's side bar is the priority colour. | `blocks.card` |
| DM thread under the card | Every comment and every status move, with who did it, their role (`you`, `manager`, `admin`) and the reason or remarks. **The side bar tells the two sides apart: teal for the manager or an admin, grey for the assignee's own.** | `blocks.comment_line`, `blocks.move_line`, `blocks.comment_color` |
| Home tab | The person's open tasks grouped by status (blocked first), each row with priority dot, task number, title, project and stage tags, due date (or "Overdue by N days") and **the date and time it was created**; a Show (status) and a Stage filter; a status dropdown, Comment and Details button per task. | `blocks.home_view`, `services/home.py` |
| Details popup | The task's fields and its timeline. A popup cannot draw a coloured bar, so each entry is a Slack quote (a line down its side) with name, role, time and, for Slack-made entries, "from Slack". | `blocks.task_detail_modal` |
| Team channel | "Added tasks" (bulk upload) or "Tasks from Standup" (standup batches): one `@mention - N tasks` line per person, and the PDF `Task-<dd-Mon-yyyy>.pdf` with the details. A single task created on the board posts nothing here; the assignee's DM is always sent. | `services/announce.py`, `pdf.py`, `messages.py` |

Slack's own labels: the `review` status reads "Review" in Slack only.

## Interactions (what the listener handles)

Each is a Slack event turned into one call; there is no logic in `listener.py`.

| Slack event | Handler | Result |
| --- | --- | --- |
| Status dropdown on a card or Home row | `on_status` | Moves straight away, or opens the reason form for Blocked and back to To Do |
| Reason form submitted / closed | `on_reason`, `on_reason_closed` | Move with the reason / card reset to the task's real status |
| Comment button, form submitted | `on_comment`, `on_comment_submit` | Comment saved on the task, marked "from Slack" |
| Details button | `on_home_details` | Opens the popup |
| Show and Stage dropdowns | `on_home_show`, `on_home_stage` | Home tab redrawn with that filter (kept in memory per person) |
| `app_home_opened` | `on_home_opened` | Home tab drawn |

## Commands and queries (command-query separation)

Commands change something and return nothing, or a problem message to show to the person; queries read and change nothing. All of them live in `services/`; Slack calls never raise into the caller: a Slack failure is logged and must not break the board action that caused it.

### Commands

| Function | File | What it does |
| --- | --- | --- |
| `outbox.record_task_added` | `outbox.py` | Queues "this task was added" for the next channel announcement. Called inside the task command's transaction. |
| `dm.record_dm` | `dm.py` | Queues the assignee's DM card. Called by the task commands before they commit. |
| `dm.record_reassignment` | `dm.py` | When a task moves to someone else: marks the current card replaced (a card never sent is dropped) and queues a new live card for the new assignee, remembering who reassigned it. One live card per task (a unique index on the rows not yet replaced). Called by `update_task` before it commits. |
| `dm.after_reassign` | `dm.py` | After the reply to a reassignment: sends the new card, then posts the hand-over under it, closes the old card (`dm.close_replaced`) and redraws both people's Home tabs. Never raises. |
| `dm.close_replaced` | `dm.py` | Redraws the card of the assignee the task just left: its title, "Reassigned to <name>", no buttons. Only the newest replaced card, so an earlier one keeps naming the person it went to. |
| `announce.flush_team` | `announce.py` | After the board request is answered: sends the channel announcement with the PDF, then the queued DM cards. A failed row is marked and can be retried. |
| `dm.send_pending` | `dm.py` | Opens each assignee's DM, posts the card, stores its `ts` so the thread can be found. |
| `dm.refresh_card` | `dm.py` | Redraws the card (buttons and status) after a change from either side. |
| `dm.remove_after_delete` | `dm.py` | After a manager deletes a task: deletes every Slack message of the task (the replies under each card first, then the card, replaced cards too) with `client.delete_message` (`chat.delete`), then redraws the assignee's Home tab. A message already gone is fine; any other Slack failure is logged and the rest are still tried. Never raises. Its input comes from the query `dm.removal_plan`, run before the delete because the delete takes the DM rows with it. |
| `dm.post_comment`, `dm.post_manager_comment`, `dm.post_move` | `dm.py` | Post a comment or a move in the card's thread with the side's bar; every posted `ts` is remembered so the whole thread can be removed a few days after Done. |
| `interactions.move` | `interactions.py` | The assignee moves their task (up to Review) through the same task command the board uses; returns a problem text or `None`. |
| `interactions.comment` | `interactions.py` | The assignee's comment through the same task command. |
| `interactions.reset_card` | `interactions.py` | Redraws a card and the Home tab from the real state after a refused move. |
| `home.publish` | `home.py` | Draws the Home tab (one database read, one Slack call). Never raises. |

### Queries

| Function | File | What it returns |
| --- | --- | --- |
| `interactions.reason_view`, `comment_view`, `details_view` | `interactions.py` | The form or popup to open, or why it cannot be opened (not your task, task is Done, ...). Read the database and Slack nothing. |
| `dm.removal_plan` | `dm.py` | For a task about to be deleted: every Slack message it has as (channel, ts), replies before their card, and the assignee's Slack id. Reads the database only; must run before the delete. |
| `blocks.*` | `blocks.py` | Pure functions: task and person in, Slack blocks out. No database, no Slack. The Home tab lists the 8 most recently completed tasks (`HOME_MAX_DONE`) read-only, below the open ones. |
| `client.*` | `client.py` | The thin Slack web API wrapper: `open_dm`, `post_message`, `update_message`, `delete_message`, `publish_home`, `post_with_pdf`. Errors become `SlackError`. |

## Folder map

```
server/slack/
├── listener.py       Socket Mode process: Slack events to service calls
├── client.py         Slack Web API calls (HTTPS), the only file that talks to Slack
├── blocks.py         every card, thread line, form, popup and the Home view as Slack blocks
├── messages.py       channel announcement wording (HEADING_BULK, HEADING_STANDUP)
├── pdf.py            the announcement PDF
└── services/
    ├── announce.py   channel post + PDF, then DM cards
    ├── dm.py         DM cards and their thread
    ├── home.py       the Home tab
    ├── interactions.py  what a button press does
    └── outbox.py     the queue of announcements
```

## When a task is reassigned

The new assignee gets their own DM card (the assignee's buttons: status dropdown and Comment), and the first message under it reads "<manager> reassigned this task to you." followed by the latest 10 comments, moves and reassignments already on the task, oldest first, as quotes with who said them (you, manager, admin, or previous assignee) and when, and a line saying how many earlier ones are not shown. The old assignee's card is closed: the title, "Reassigned to <name>", no buttons, so they cannot move it from there (the server also refuses). Anything said afterwards, from the board or from Slack, goes under the new card. Both people's Home tabs are redrawn. If the new assignee has no real Slack id nothing is sent to them (the old card is still closed); if Slack refuses the card it is tried again like any other, and the hand-over follows it. The earlier thread itself is not copied: its content is on the task's timeline, and the hand-over is a summary of that.

## Not done or not checked

- Not tried against a real Slack workspace in this session; tests fake Slack (`server/tests/test_slack_*.py`).
- Home tab filters live in the listener's memory and reset when it restarts.
- A retried announcement can carry the other source's heading (the heading is not stored per row).
- The alert for tasks due within 2 days is not built.
