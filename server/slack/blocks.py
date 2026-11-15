"""The task card an assignee gets in a DM, as Slack Block Kit. Pure: a task and who it is for in, blocks out.

The status control is a dropdown of the statuses the assignee may move the task to, taken from the same rule the server
enforces (`security.authorization.assignee_transitions_for`), so the card never offers something the server would refuse.
They can move between To Do, In Progress, Blocked and In Review, backwards included, and never to Done: the manager decides
that. Once the task is Done the card is locked (no dropdown, no Comment) and shows the reviewer's last remarks. A Comment
button is there until then.

Slack does not let an app colour its own controls, so the app's colour is the bar down the card's left side, by priority like
the board's cards.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from models import Person, Task
from security.authorization import ASSIGNEE_REASON_STATUSES, ASSIGNEE_STATUSES, assignee_transitions_for, can_assignee_comment
from slack.messages import escape
from tasks.rules import is_due_soon, is_overdue

SITE_TZ = ZoneInfo("Asia/Kolkata")
STATUS_LABEL = {"todo": "To Do", "in_progress": "In Progress", "blocked": "Blocked", "review": "Review", "done": "Done"}
STATUS_ACTION = "wb_status"  # the dropdown's action_id; the chosen option's value is "<task id>|<status>"
COMMENT_ACTION = "wb_comment"
# The card's bar by priority, the board's own tokens (client/src/styles/globals.css): danger, warning and brand.
PRIORITY_COLOR = {"high": "#cf3f3f", "medium": "#a75c09", "low": "#3cbfad"}
HOME_STAGE_ACTION = "wb_home_stage"  # the Home tab's Stage dropdown; its value is the stage, or HOME_ALL
HOME_ALL = "__all__"
HOME_ORDER = ("blocked", "in_progress", "review", "todo")  # open statuses, what needs the person most first
HOME_STATUS_FILTER_ACTION = "wb_home_show"  # the Home tab's Show dropdown; its value is a status, or HOME_ALL
HOME_DETAILS_ACTION = "wb_home_details"  # the row's Details button; its value is the task id
HOME_MAX_TASKS = 20  # a Home tab holds at most 100 blocks and a task is three of them (row, controls, divider)
THREAD_MAX_ENTRIES = 15  # the newest timeline entries the Details popup shows
# Slack cannot colour text on a Home tab, so colour is carried by emoji: a dot for the task's priority (the board's red,
# amber and green) and a square for each status group.
PRIORITY_DOT = {"high": ":red_circle:", "medium": ":large_yellow_circle:", "low": ":large_green_circle:"}
STATUS_MARK = {"blocked": ":large_red_square:", "in_progress": ":large_blue_square:", "review": ":large_purple_square:", "todo": ":white_large_square:"}
REASON_TITLE = {"blocked": "Why is it blocked?", "todo": "Why move it back?"}  # a modal's title is at most 24 characters


def _due(value: date | None) -> str:
    return value.strftime("%a %-d %b") if value else "No due date"


def _created(task: Task) -> str:
    """The day the task was created, on the Indian calendar like every other date in the app."""
    created = task.created_at or datetime.now(SITE_TZ)  # empty only on a task not yet saved
    return created.astimezone(SITE_TZ).strftime("%a %-d %b")


def _created_at(task: Task) -> str:
    """The day and time the task was created, Indian time, as the Home tab's row shows it."""
    created = task.created_at or datetime.now(SITE_TZ)
    return created.astimezone(SITE_TZ).strftime("%a %-d %b, %-I:%M %p")


def card_color(task: Task) -> str:
    return PRIORITY_COLOR.get(task.priority, PRIORITY_COLOR["medium"])


def task_code(task: Task) -> str:
    """The task's short id as the card shows it ("Task #33"), the same number the Workboard shows when the task is opened."""
    return f"Task #{task.number}"


def needs_reason(to: str) -> bool:
    return to in ASSIGNEE_REASON_STATUSES


def card(task: Task, assignee: Person, reviewer_note: tuple[str, str] | None = None) -> tuple[str, list[dict]]:
    """(text for notifications, blocks) for the task's DM card in its current state. `reviewer_note` is (who, remarks) of the
    manager's last Done entry, shown once the task is locked."""
    status = STATUS_LABEL.get(task.status, task.status)
    lines = [f"*{task_code(task)}*  {escape(task.title)}"]
    if task.description.strip():
        lines.append(escape(task.description.strip()))
    blocks: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]
    tags = [f"`{escape(label)}`" for label in (task.project, task.stage) if label]
    if tags:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "  ".join(tags)}]})
    blocks += [
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Priority*\n{task.priority.capitalize()}"},
                {"type": "mrkdwn", "text": f"*Created*\n`{_created(task)}`"},
                {"type": "mrkdwn", "text": f"*Due*\n`{_due(task.due_at)}`"},
                {"type": "mrkdwn", "text": f"*Status*\n{status}"},
            ],
        },
    ]
    if controls := _controls(task, assignee):
        blocks.append({"type": "actions", "block_id": f"wb_actions_{task.id}", "elements": controls})
    if task.status == "review":
        blocks.append(_note("Waiting for your manager to review it. You can still move it back."))
    elif task.status == "done":
        blocks.append(_note("Done. This task is locked, and this thread will be removed a few days after."))
        if reviewer_note and reviewer_note[1].strip():
            who, remarks = reviewer_note
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{escape(who)}* · reviewer\n{escape(remarks.strip())}"}})
    return f"{task_code(task)} {task.title} ({status})", blocks


def _controls(task: Task, assignee: Person) -> list[dict]:
    """What the assignee may do to the task: the status dropdown and the Comment button, each only while the server allows it."""
    controls: list[dict] = []
    if assignee_transitions_for(assignee, task):
        controls.append(_status_select(task))
    if can_assignee_comment(assignee, task):
        controls.append({"type": "button", "action_id": COMMENT_ACTION, "text": {"type": "plain_text", "text": "Comment"}, "value": str(task.id)})
    return controls


def _option(task: Task, status: str) -> dict:
    return {"text": {"type": "plain_text", "text": STATUS_LABEL[status]}, "value": f"{task.id}|{status}"}


def _status_select(task: Task) -> dict:
    """The status dropdown: every status the assignee can set, with the current one selected."""
    return {
        "type": "static_select",
        "action_id": STATUS_ACTION,
        "placeholder": {"type": "plain_text", "text": "Change status"},
        "options": [_option(task, s) for s in ASSIGNEE_STATUSES],
        "initial_option": _option(task, task.status),
    }


def _note(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


# The bar beside a comment tells the two sides apart: the manager's (or an admin's) in the app's teal, the assignee's own in
# a neutral grey. (Slack cannot right-align a message, and the two-column trick collapses in the narrow Thread panel.)
MANAGER_BAR = "#3cbfad"
ASSIGNEE_BAR = "#c9cfdd"


def comment_line(author: str, role: str, text: str) -> tuple[str, list[dict]]:
    """A comment as it appears in the card's thread: who said it and in what role, then what they said."""
    body = f"*{escape(author)}* · {escape(role)}\n{escape(text)}"
    return f"{author}: {text}", [{"type": "section", "text": {"type": "mrkdwn", "text": body}}]


def comment_color(role: str) -> str:
    return ASSIGNEE_BAR if role == "you" else MANAGER_BAR


def move_line(author: str, role: str, to: str, note: str) -> tuple[str, list[dict]]:
    """A status move with its reason as it appears in the card's thread: who moved it and where, then the reason as a quote
    (the remarks, for Done), so the assignee can see why."""
    label = STATUS_LABEL.get(to, to)
    quoted = "\n".join(f"> {line}" for line in escape(note.strip()).splitlines() if line.strip())
    body = f"*{escape(author)}* · {escape(role)}\nMoved it to *{label}*" + (f"\n{quoted}" if quoted else "")
    return f"{author} moved it to {label}" + (f": {note.strip()}" if quoted else ""), [{"type": "section", "text": {"type": "mrkdwn", "text": body}}]


def reason_modal(task: Task, to: str) -> dict:
    """The small form asked when a move needs a reason (Blocked, or back to To Do): the same reason the board asks for.
    Closing it without sending tells the listener, which resets the dropdown to the task's real status."""
    return {
        "type": "modal",
        "callback_id": "wb_reason",
        "notify_on_close": True,
        "private_metadata": f"{task.id}|{to}",
        "title": {"type": "plain_text", "text": REASON_TITLE.get(to, "Why?")},
        "submit": {"type": "plain_text", "text": f"Move to {STATUS_LABEL.get(to, to)}"[:24]},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reason",
                "label": {"type": "plain_text", "text": "Reason"},  # Slack needs a label; the task is already on the card behind
                "element": {"type": "plain_text_input", "action_id": "text", "multiline": True, "max_length": 500},
            }
        ],
    }


def comment_modal(task: Task) -> dict:
    """The form the Comment button opens. The comment goes on the task and into this card's thread."""
    return {
        "type": "modal",
        "callback_id": "wb_comment_submit",
        "private_metadata": str(task.id),
        "title": {"type": "plain_text", "text": "Add a comment"},
        "submit": {"type": "plain_text", "text": "Post comment"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "comment",
                "label": {"type": "plain_text", "text": task.title[:150]},
                "element": {"type": "plain_text_input", "action_id": "text", "multiline": True, "max_length": 1000},
            }
        ],
    }


# ---- the Home tab: the person's open tasks, with the same controls as the DM card ----

def _details_button(task: Task) -> dict:
    return {"type": "button", "action_id": HOME_DETAILS_ACTION, "text": {"type": "plain_text", "text": "Details"}, "value": str(task.id)}


def _overdue_by(task: Task, today: date) -> str:
    days = (today - task.due_at).days
    return f"Overdue by {days} {'day' if days == 1 else 'days'}"


def _home_row(task: Task, today: date) -> dict:
    due = f"*{_overdue_by(task, today)}*" if is_overdue(task, today) else f"Due {_due(task.due_at)}" if task.due_at else "No due date"
    tags = [f"`{escape(label)}`" for label in (task.project, task.stage) if label]
    line = " · ".join([*(["  ".join(tags)] if tags else []), due, f"Created {_created_at(task)}"])
    text = f"{PRIORITY_DOT.get(task.priority, PRIORITY_DOT['medium'])} *{task_code(task)}*  {escape(task.title)}\n{line}"
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _stage_select(stages: list[str], chosen: str | None) -> dict:
    options = [{"text": {"type": "plain_text", "text": "All stages"}, "value": HOME_ALL}]
    options += [{"text": {"type": "plain_text", "text": s[:75]}, "value": s[:75]} for s in stages]
    initial = next((o for o in options if o["value"] == (chosen or HOME_ALL)), options[0])
    return {"type": "static_select", "action_id": HOME_STAGE_ACTION, "options": options, "initial_option": initial}


def _show_select(open_tasks: list[Task], chosen: str | None) -> dict:
    """The "Show" dropdown at the top: all open tasks or one status, each with how many tasks it holds."""
    options = [{"text": {"type": "plain_text", "text": f"All ({len(open_tasks)})"}, "value": HOME_ALL}]
    for status in HOME_ORDER:
        n = sum(t.status == status for t in open_tasks)
        options.append({"text": {"type": "plain_text", "text": f"{STATUS_LABEL[status]} ({n})"}, "value": status})
    initial = next((o for o in options if o["value"] == (chosen or HOME_ALL)), options[0])
    return {"type": "static_select", "action_id": HOME_STATUS_FILTER_ACTION, "options": options, "initial_option": initial}


def home_view(person: Person, tasks: list[Task], today: date, stage: str | None = None, status: str | None = None) -> dict:
    """The Home tab of the bot for `person`: their open tasks grouped by status (blocked first), each with its status dropdown
    and Comment button. A Show dropdown (one status) and a Stage dropdown narrow the list. Done tasks are left out; at most
    HOME_MAX_TASKS are shown."""
    open_tasks = [t for t in tasks if t.status != "done"]
    stages = sorted({t.stage for t in open_tasks if t.stage}, key=str.lower)
    shown = [t for t in open_tasks if (not stage or t.stage == stage) and (not status or t.status == status)]
    first_name = (person.name or "there").split()[0]
    overdue, soon = sum(is_overdue(t, today) for t in open_tasks), sum(is_due_soon(t, today) for t in open_tasks)
    summary = f"{len(open_tasks)} open"
    summary += f" · *{overdue} overdue*" if overdue else ""
    summary += f" · {soon} due in the next 2 days" if soon else ""
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Your tasks, {first_name}"[:150]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": summary if open_tasks else "Nothing open right now."}]},
    ]
    if open_tasks:
        legend = "  ".join(f"{dot} {name}" for name, dot in (("High", PRIORITY_DOT["high"]), ("Medium", PRIORITY_DOT["medium"]), ("Low", PRIORITY_DOT["low"])))
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"Priority  {legend}"}]})
    if open_tasks:
        filters = [_show_select(open_tasks, status)] + ([_stage_select(stages, stage)] if stages else [])
        blocks.append({"type": "actions", "block_id": "wb_home_filter", "elements": filters})
    if not shown:
        if open_tasks:
            blocks.append(_note("No open tasks match this filter. Choose All to see everything."))
        return {"type": "home", "blocks": blocks}
    count = 0
    for group_status in HOME_ORDER:
        group = sorted((t for t in shown if t.status == group_status), key=lambda t: (t.due_at is None, t.due_at or date.max, t.number))
        if not group or count >= HOME_MAX_TASKS:
            continue
        blocks += [{"type": "divider"}, {"type": "section", "text": {"type": "mrkdwn", "text": f"{STATUS_MARK[group_status]}  *{STATUS_LABEL[group_status]}*  ({len(group)})"}}]
        for index, task in enumerate(group):
            if count >= HOME_MAX_TASKS:
                break
            if index:
                blocks.append({"type": "divider"})  # between the tasks of a group; the next group brings its own divider
            blocks.append(_home_row(task, today))
            blocks.append({"type": "actions", "block_id": f"wb_home_{task.id}", "elements": [*_controls(task, person), _details_button(task)]})
            count += 1
    if count < len(shown):
        blocks.append(_note(f"Showing the first {count} of {len(shown)} tasks. Finish or move some to see the rest."))
    return {"type": "home", "blocks": blocks}


def _thread_entry(
    who: str, role: str, kind: str, field: str | None, old: str | None, new: str | None, note: str | None, source: str, when: datetime
) -> str:
    """One timeline entry as a few lines of Slack text: who (and their role), what they did, then the reason or comment. A
    popup cannot draw the coloured bar the DM thread has, so the whole entry is a quote, which Slack draws with a line down
    its side."""
    stamp = when.astimezone(SITE_TZ).strftime("%a %-d %b, %-I:%M %p") + (" · from Slack" if source == "slack" else "")
    head = f"*{escape(who)}*{f' · {role}' if role else ''}  {stamp}"
    if kind == "comment":
        what = ""
    elif kind == "status":
        what = f"Moved it to *{STATUS_LABEL.get(new or '', escape(new or ''))}*"
    elif kind == "created":
        what = "Created the task"
    elif kind == "reassign":
        what = f"Changed the assignee: {escape(old or 'nobody')} → {escape(new or 'nobody')}"
    else:
        what = f"Changed {escape((field or 'a field').lower())}: {escape(old or 'none')} → {escape(new or 'none')}"
    quote = "\n".join(f"> {escape(line)}" for line in (note or "").strip().splitlines())
    return "\n".join(f"> {line}" if not line.startswith("> ") else line for part in (head, what, quote) if part for line in part.splitlines())


def task_detail_modal(task: Task, thread: list[tuple], can_comment: bool = False) -> dict:
    """The popup the Details button opens: the task's fields, then its thread, oldest first. `thread` holds
    (who, role, kind, field, old, new, note, source, when) for the newest THREAD_MAX_ENTRIES timeline entries. When the person may
    still comment, a comment box ends it and its Comment button saves it through the same handler as the Comment form."""
    status = STATUS_LABEL.get(task.status, task.status)
    lines = [f"*{task_code(task)}*  {escape(task.title)}"]
    if task.description.strip():
        lines.append(escape(task.description.strip())[:2500])
    blocks: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]
    if tags := [f"`{escape(label)}`" for label in (task.project, task.stage) if label]:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "  ".join(tags)}]})
    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*Priority*\n{PRIORITY_DOT.get(task.priority, '')} {task.priority.capitalize()}"},
            {"type": "mrkdwn", "text": f"*Status*\n{status}"},
            {"type": "mrkdwn", "text": f"*Created*\n`{_created(task)}`"},
            {"type": "mrkdwn", "text": f"*Due*\n`{_due(task.due_at)}`"},
        ],
    })
    blocks += [{"type": "divider"}, {"type": "section", "text": {"type": "mrkdwn", "text": "*Thread*"}}]
    if not thread:
        blocks.append(_note("Nothing yet."))
    for entry in thread:
        blocks += [{"type": "section", "text": {"type": "mrkdwn", "text": _thread_entry(*entry)[:2900]}}, {"type": "divider"}]
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": task_code(task)[:24]},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": blocks,
    }
    if can_comment:
        blocks.append({
            "type": "input",
            "block_id": "comment",  # the ids the Comment form's handler reads
            "label": {"type": "plain_text", "text": "Comment"},
            "element": {"type": "plain_text_input", "action_id": "text", "multiline": True, "max_length": 1000},
        })
        view |= {"callback_id": "wb_comment_submit", "private_metadata": str(task.id), "submit": {"type": "plain_text", "text": "Comment"}}
    return view


def home_unknown_view() -> dict:
    return {
        "type": "home",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "I could not find you in the Work Board directory, so there are no tasks to show."}}],
    }
