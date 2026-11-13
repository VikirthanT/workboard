"""Names and limits for the standups feature."""
# Suggestions nobody has acted on, and rejected ones, are removed this many days after they became so. A rejected one
# can be restored until then. Approved ones are kept (they are the link from a task back to its standup).
KEEP_DAYS = 3

# How far back a sync (and the standup shown above a person's suggestions) looks.
SYNC_DAYS = 14
