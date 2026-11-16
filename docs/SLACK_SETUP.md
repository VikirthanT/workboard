# Slack app setup

How to create the Work Board's Slack app, for a test workspace first. The app posts task announcements to a team's standup channel and (later) sends task DMs with buttons. **None of that code is built yet**: this only creates the app and gets its two tokens, so the code can be tried against it. The standup posts themselves come from the standup app's database, not from Slack, so this app never reads channel messages.

## 1. Create the app

1. Go to <https://api.slack.com/apps> and choose **Create New App**, then **From an app manifest**.
2. Pick the workspace (use a test workspace or a dummy channel first).
3. Paste the contents of `docs/slack-app-manifest.json` as JSON and create the app. If Slack flags a field, tell whoever maintains this file: the manifest has not been tried in a real workspace yet.

What the manifest sets, and why:

| Setting | Why |
| --- | --- |
| Socket Mode on | The app connects out to Slack, so it needs no public URL. |
| Interactivity on | Buttons and modals in task cards. |
| Messages tab read only | Turns off the typing box in the bot's DMs, so an assignee can only answer through the buttons and modal, and the bot can delete the whole thread later. |
| `chat:write` | Post messages, and delete the bot's own. |
| `files:write` | Upload the PDF. |
| `im:write` | Open a DM with an assignee. |
| `users:read`, `users:read.email` | Match a Slack person to the directory by email. |
| `channels:read`, `groups:read` | Look up a team's channel (public or private). |

## 2. Get the two tokens

1. **App-level token:** *Basic Information*, then *App-Level Tokens*, then *Generate Token and Scopes*. Give it the `connections:write` scope. It starts with `xapp-`.
2. **Bot token:** *Install App*, then *Install to Workspace* (a Slack admin may need to approve it). Then *OAuth & Permissions*, **Bot User OAuth Token**. It starts with `xoxb-`.

Put them in `.env` yourself, as `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` (see `.env.example`). Never commit them or paste them in a chat.

## 3. Add the bot to the channel

In the team's standup channel (or the dummy one): `/invite @Work Board`. A bot can only post to channels it is in.

## 4. Give the team the channel

Copy the channel's id (channel details, at the bottom: it looks like `C0123ABCD`) and set it as the team's standup channel in the admin Teams portal. The same channel is used both for reading the team's standup and for posting the announcements.

## Not built yet

The code that uses these tokens: the post to the channel tagging each assignee, the PDF, and the DMs with two-way sync. See `refdocs/checklist.md`.
