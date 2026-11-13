"""The task card an assignee gets in a DM, as Slack Block Kit. Pure: a task and who it is for in, blocks out.

The status control is a dropdown of the statuses the assignee may move the task to, taken from the same rule the server
enforces (`security.authorization.assignee_transitions_for`), so the card never offers something the server would refuse.
They can move between To Do, In Progress, Blocked and In Review, backwards included, and never to Done: the manager decides
that. Once the task is Done the card is locked (no dropdown, no Comment) and shows the reviewer's last remarks. A Comment
button is there until then.

Slack does not let an app colour its own controls, so the app's colour is the bar down the card's left side, by priority like
the board's cards.
"""
from datetime import date

from models import Person, Task
from security.authorization import ASSIGNEE_REASON_STATUSES, ASSIGNEE_STATUSES, assignee_transitions_for, can_assignee_comment
from slack.messages import escape

STATUS_LABEL = {"todo": "To Do", "in_progress": "In Progress", "blocked": "Blocked", "review": "Review", "done": "Done"}
STATUS_ACTION = "wb_status"  # the dropdown's action_id; the chosen option's value is "<task id>|<status>"
COMMENT_ACTION = "wb_comment"
# The card's bar by priority, the board's own tokens (client/src/styles/globals.css): danger, warning and brand.
PRIORITY_COLOR = {"high": "#cf3f3f", "medium": "#a75c09", "low": "#3cbfad"}
REASON_TITLE = {"blocked": "Why is it blocked?", "todo": "Why move it back?"}  # a modal's title is at most 24 characters


def _due(value: date | None) -> str:
    return value.strftime("%a %-d %b") if value else "No due date"


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
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Priority*\n{task.priority.capitalize()}"},
                {"type": "mrkdwn", "text": f"*Due*\n{_due(task.due_at)}"},
                {"type": "mrkdwn", "text": f"*Status*\n{status}"},
            ],
        },
    ]
    controls: list[dict] = []
    if assignee_transitions_for(assignee, task):
        controls.append(_status_select(task))
    if can_assignee_comment(assignee, task):
        controls.append({"type": "button", "action_id": COMMENT_ACTION, "text": {"type": "plain_text", "text": "Comment"}, "value": str(task.id)})
    if controls:
        blocks.append({"type": "actions", "block_id": f"wb_actions_{task.id}", "elements": controls})
    if task.status == "review":
        blocks.append(_note("Waiting for your manager to review it. You can still move it back."))
    elif task.status == "done":
        blocks.append(_note("Done. This task is locked, and this thread will be removed a few days after."))
        if reviewer_note and reviewer_note[1].strip():
            who, remarks = reviewer_note
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{escape(who)}* · reviewer\n{escape(remarks.strip())}"}})
    return f"{task_code(task)} {task.title} ({status})", blocks


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
                "label": {"type": "plain_text", "text": task.title[:150]},
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
