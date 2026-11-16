"""Turn one standup submission into checked task suggestions.

The model proposes; this module decides what is kept. An item survives only if its quote really is in the entry, it
and is not a repeat of something the person already has tracked; at most MAX_PER_PERSON are kept, in the order the model ranked them
(items that fail a check do not use up a place). Nothing is saved
here: the caller stores what comes back.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta

from standups.llm import prompt
from standups.llm.provider import complete_json
from standups.standup_db.reader import Submission

MAX_PER_PERSON = 10  # the model is told to keep only the most important; the code holds it to that
MIN_QUOTE_WORDS = 3
SIMILAR_SHARE = 0.75  # titles sharing this much of the shorter one's words mean the same thing


@dataclass(frozen=True)
class Tracked:
    """A task or suggestion the team already has. `mine` is true when it belongs to the person being read."""
    title: str
    status: str
    owner: str
    mine: bool


@dataclass(frozen=True)
class Suggestion:
    title: str
    description: str
    kind: str
    assignee: str
    due: date | None
    priority: str
    evidence_quote: str
    subtasks: list[str]
    related_to: str | None


def norm(text: str) -> str:
    """Lower case, with list bullets, markdown marks and runs of spaces removed, so a quote matches its source."""
    return re.sub(r"\s+", " ", re.sub(r"[*_`•\-]|^\s*\d+[.)]\s*", " ", text.lower(), flags=re.M)).strip()


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - {"the", "a", "an", "to", "for", "of", "and", "with", "on", "in"}


def similar(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= SIMILAR_SHARE


def entry_text(sub: Submission) -> str:
    """What the model reads: the three sections when this week has text, otherwise the combined or raw text."""
    if not (sub.this_week or "").strip():
        return (sub.combined or "").strip() or sub.raw_content
    sections = (("LAST WEEK", sub.last_week), ("THIS WEEK", sub.this_week), ("BLOCKERS", sub.blockers))
    return "\n\n".join(f"{heading}:\n{body}" for heading, body in sections if body and body.strip())


def extract(sub: Submission, tracked: list[Tracked]) -> list[Suggestion]:
    text = entry_text(sub)
    answer = complete_json(
        prompt.PROMPT.format(
            date=sub.standup_date,
            week_start=sub.standup_date,
            week_end=sub.standup_date + timedelta(days=4),
            max_items=MAX_PER_PERSON,
            tracked="\n".join(f"- {t.title} ({t.status}, {t.owner})" for t in tracked) or "(nothing yet)",
            name=sub.person_name,
            text=text,
        ),
        prompt.SCHEMA,
    )
    items = answer.get("items")
    if not isinstance(items, list):
        return []

    source = norm(text)  # also what a due_text phrase must appear in
    tracked_titles = {t.title.strip().lower(): t.title for t in tracked}
    mine = [t.title for t in tracked if t.mine]
    kept: list[Suggestion] = []
    for raw in items:
        if len(kept) == MAX_PER_PERSON:
            break
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        description = str(raw.get("description") or "").strip()
        quote = str(raw.get("evidence_quote") or "").strip()
        if not title or not description:
            continue
        if len(norm(quote).split()) < MIN_QUOTE_WORDS or norm(quote) not in source:
            continue
        related = tracked_titles.get(str(raw.get("related_to") or "").strip().lower())
        if related is None and any(similar(title, existing) for existing in mine + [s.title for s in kept]):
            continue
        kept.append(
            Suggestion(
                title=title,
                description=description,
                kind=_choice(raw.get("kind"), prompt.KINDS, "new"),
                assignee=str(raw.get("assignee") or sub.person_name).strip() or sub.person_name,
                due=_resolve_due(raw.get("due"), raw.get("due_text"), sub.standup_date, source),
                priority=_choice(raw.get("priority"), prompt.PRIORITIES, "medium"),
                evidence_quote=quote,
                subtasks=[str(s).strip() for s in raw.get("subtasks") or [] if str(s).strip()],
                related_to=related,
            )
        )
    return kept


WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3,
    "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


def _resolve_due(model_due, phrase, standup_date: date, source: str) -> date | None:
    """A weekday named in the entry ("by Wednesday") is worked out here, not taken from the model: small models are
    often a day or more out. It is the first such weekday on or after the standup's date. The phrase must really be in
    the entry. Otherwise the model's own date is used, if it is not before the standup (a deadline cannot precede it)."""
    text = str(phrase or "").strip()
    if text and norm(text) in source:
        for word in re.findall(r"[a-z]+", text.lower()):
            if word in WEEKDAYS:
                return standup_date + timedelta(days=(WEEKDAYS[word] - standup_date.weekday()) % 7)
    chosen = _date(model_due)
    return chosen if chosen is not None and chosen >= standup_date else None


def _choice(value, allowed: tuple[str, ...], fallback: str) -> str:
    """The model's value when it is one of the allowed ones, otherwise the fallback."""
    return value if isinstance(value, str) and value in allowed else fallback


def _date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None
