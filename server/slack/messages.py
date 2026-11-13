"""The text of the announcement in the team's channel: who got how many new tasks."""
import re

from slack.pdf import AnnouncedTask, by_person

REAL_SLACK_ID = re.compile(r"^[UW][A-Z0-9]{6,}$")


def escape(text: str) -> str:
    """Slack reads &, < and > in a message as markup, so a task title cannot carry them as they are."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def person(task: AnnouncedTask) -> str:
    """A tag that notifies them when the directory has their real Slack id, otherwise just their name in bold
    (the demo people have made-up ids, which Slack would show as plain text)."""
    if task.assignee_slack_id and REAL_SLACK_ID.match(task.assignee_slack_id):
        return f"<@{task.assignee_slack_id}>"
    return f"*{escape(task.assignee_name)}*"


# The first line of the channel post: change the wording here.
HEADING_BULK = "Added tasks"  # a bulk upload
HEADING_STANDUP = "Tasks from Standup"  # tasks added from the standup suggestions


def announcement(tasks: list[AnnouncedTask], heading: str = HEADING_BULK) -> str:
    """Only who got how many: the titles, dates and priorities are in the PDF."""
    lines = [f"*{heading}*"]
    for rows in by_person(tasks).values():
        lines += ["", f"{person(rows[0])} - {len(rows)} {'task' if len(rows) == 1 else 'tasks'}"]
    lines += ["", "The PDF has the details. For updates, see your Slack DM from the Workboard bot."]
    return "\n".join(lines)
