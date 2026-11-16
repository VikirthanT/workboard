"""Names and limits for the standups feature."""
from datetime import date, timedelta

# Suggestions nobody has acted on, and rejected ones, are removed this many days after they became so. A rejected one
# can be restored until then. Approved ones are kept (they are the link from a task back to its standup).
KEEP_DAYS = 3



def week_start(today: date) -> date:
    """The Monday of `today`'s week. A sync, and the standup shown above a person's suggestions, read only standups dated on
    or after it: this week's, never an earlier week's (so "Standup not found" means nothing this week)."""
    return today - timedelta(days=today.weekday())
