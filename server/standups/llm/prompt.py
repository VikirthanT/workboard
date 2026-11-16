"""The extraction prompt and the shape of the answer. `PROMPT_HASH` is stored on every suggestion, so a suggestion can
be traced to the exact wording that produced it."""
import hashlib
import json

KINDS = ("blocker", "deadline", "handover", "carry_over", "new")
PRIORITIES = ("high", "medium", "low")

PROMPT = """You are the engineer's manager. From their weekly standup, list the tasks that need to be created and monitored on the board for them this week, and leave out everything else. Think like someone who has to follow each task up: if you would not ask about it next Monday, it is not a task.

The standup was posted on {date}. LAST WEEK is what they did. THIS WEEK is what they plan for {week_start} to {week_end}. BLOCKERS are things stopping them.

A task is one deliverable the manager could check next Monday as done or not done.
- Merge related lines into one task and list the parts as subtasks. Example: the lines "Table", "Station layout" and "Mounting plate" under "BITS Designs" become one task "Complete BITS station designs".
- Take planned work from THIS WEEK, unfinished work from LAST WEEK that continues, and each blocker (the task is to get it unblocked).
- Do not make tasks from: work finished last week, vague headings with nothing to deliver, status notes, thanks, or anything already tracked (below).
- Leave, holiday and availability notes ("on leave 26/10 to 6/11", "out Friday") are not tasks. The one exception is a stated handover of work before the leave: then make one handover task.
- Leave out small routine items that need no follow-up (reading an email, attending a regular meeting, a quick reply) unless they have a date or are blocking someone. Keep what has a clear outcome, a date, a dependency on another person, or a blocker.
- Give at most {max_items} tasks and only the really important ones, most important first (blockers and dated items before routine work). Aim for at least 3 or 4 when the entry supports that many, but never invent one: each task needs a real quote, so fewer, even none, is right when the entry has fewer.

Already tracked for this team (open tasks and suggestions still waiting), with status and owner:
{tracked}
Do not make a task that means the same as one of these for the same person. If a blocker or carry-over line is about work that is already In Progress, skip it. If it is a clearly new obstacle to that work, make the task and set related_to to the tracked task's exact title; otherwise related_to is null.

Fields for each task:
- title: verb + object, at most 8 words, in your own wording.
- description: one sentence saying what done looks like this week. Never just repeat the quote.
- kind: blocker, deadline (a date is stated), handover, carry_over (unfinished from last week), or new.
- assignee: the submitter unless the text clearly names someone else.
- due_text: the words in the entry that state a deadline, copied exactly (for example "by Wednesday" or "26/10"), or null when none is stated.
- due: YYYY-MM-DD only if the text states a date, never earlier than {date}; otherwise null. For a weekday deadline just copy the words into due_text and leave due null, the date is worked out afterwards.
- priority: high for blockers and dated items, low for housekeeping and documentation, otherwise medium.
- evidence_quote: one line copied exactly from the entry that supports the task. At least 3 words, never a bare bullet or heading.
- subtasks: the merged parts, or an empty list.
- related_to: a tracked task's exact title, or null.

Submitter: {name}
Entry:
{text}
"""

_FIELDS = {
    "title": {"type": "string"},
    "description": {"type": "string"},
    "kind": {"type": "string", "enum": list(KINDS)},
    "assignee": {"type": "string"},
    "due_text": {"type": ["string", "null"]},
    "due": {"type": ["string", "null"]},
    "priority": {"type": "string", "enum": list(PRIORITIES)},
    "evidence_quote": {"type": "string"},
    "subtasks": {"type": "array", "items": {"type": "string"}},
    "related_to": {"type": ["string", "null"]},
}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": list(_FIELDS), "properties": _FIELDS},
        }
    },
}

PROMPT_HASH = hashlib.sha256((PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()
