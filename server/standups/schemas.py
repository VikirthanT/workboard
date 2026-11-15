import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from tasks.states import MAX_DESCRIPTION_LENGTH, MAX_TITLE_LENGTH


class ChannelResponse(BaseModel):
    """A standup channel as the standup app knows it. `slack_channel_id` is what a team stores."""
    slack_channel_id: str
    name: str


class ChannelNameResponse(BaseModel):
    """A Slack channel looked up by its id: the name Slack shows for it."""
    id: str
    name: str


class SuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_id: uuid.UUID
    title: str
    description: str
    kind: str
    priority: str
    start_at: date | None
    due_at: date | None
    # True when the standup stated no date and due_at is the Friday default.
    due_is_default: bool
    subtasks: list[str]
    evidence_quote: str
    # The title of an already-tracked task this one is a new obstacle to, or null.
    related_to: str | None
    state: str
    late_reply: bool
    standup_date: date
    task_id: uuid.UUID | None


class StandupResponse(BaseModel):
    """What the person posted. Three sections when they used them; otherwise `message` holds the whole post and the
    sections are null."""
    date: date
    # When they actually posted; the page shows this, not the standup's date.
    posted_at: datetime | None
    late_reply: bool
    last_week: str | None
    this_week: str | None
    blockers: str | None
    message: str | None


class SuggestionPerson(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str


class PersonSuggestionsResponse(BaseModel):
    person: SuggestionPerson
    # null when they posted nothing in the recent window (or the standup database cannot be read).
    standup: StandupResponse | None
    suggestions: list[SuggestionResponse]


class SuggestionsPageResponse(BaseModel):
    standup_channel_id: str | None
    last_synced_at: datetime | None
    # Why the standup posts could not be shown: "not_configured", "unreadable" or "channel_empty"; null when posts were found.
    standup_problem: str | None
    people: list[PersonSuggestionsResponse]


class SuggestionEdit(BaseModel):
    """Only the fields sent are changed; a date may be sent as null to clear it."""
    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    priority: str | None = Field(default=None, max_length=10)
    person_id: uuid.UUID | None = None
    start_at: date | None = None
    due_at: date | None = None


class AddSuggestions(BaseModel):
    suggestion_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
