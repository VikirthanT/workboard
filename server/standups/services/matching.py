"""Which of a team's people posted a standup submission. The standup app has its own list of persons, so the match is
by Slack id first and then by email; anyone who matches neither is not read."""
from typing import Callable

from models import Person
from standups.standup_db.reader import Submission


def person_matcher(members: list[Person]) -> Callable[[Submission], Person | None]:
    by_slack = {p.slack_user_id: p for p in members if p.slack_user_id}
    by_email = {p.email.lower(): p for p in members if p.email}

    def match(sub: Submission) -> Person | None:
        return by_slack.get(sub.slack_user_id or "") or by_email.get((sub.email or "").lower())

    return match
