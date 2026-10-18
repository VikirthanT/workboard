"""Audit action names written to access_audit_log."""
TEAM_CREATE = "team.create"
TEAM_MANAGER_CHANGE = "team.manager_change"
TEAM_DELETE = "team.delete"
MEMBER_ADD = "member.add"
MEMBER_REMOVE = "member.remove"
ADMIN_GRANT = "admin.grant"
ADMIN_REVOKE = "admin.revoke"
# Written by the tasks feature into the same append-only log. A deleted task takes its own timeline with it, so the
# delete entry carries a snapshot of the task and that timeline in `details`.
TASK_DELETE = "task.delete"
TASK_REASSIGN = "task.reassign"

MAX_REASON_LENGTH = 500

# Slack ids of the development demo accounts (seed/demo_db.py) start with this. The directory load leaves them alone.
DEMO_SLACK_PREFIX = "DEMO-"

# Paged lists (/people, /audit-log): the page size a client gets by default, and the most it may ask for.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
