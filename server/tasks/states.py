"""Limits and names for the tasks feature. Mirrors the checks in client/src/mocks/handlers.ts."""
MAX_TITLE_LENGTH = 140
MAX_DESCRIPTION_LENGTH = 5000
MAX_NOTE_LENGTH = 500  # the reason or remarks on a status move
MAX_COMMENT_LENGTH = 1000

# Timeline field labels written to task_activity.field (the client shows them as they are).
FIELD_TITLE = "title"
FIELD_DESCRIPTION = "description"
FIELD_PRIORITY = "priority"
FIELD_DUE = "due date"
FIELD_ASSIGNEE = "assignee"
FIELD_STATUS = "status"
