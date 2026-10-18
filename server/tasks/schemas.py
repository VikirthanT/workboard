import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tasks.states import MAX_COMMENT_LENGTH, MAX_DESCRIPTION_LENGTH, MAX_NOTE_LENGTH, MAX_TITLE_LENGTH

Priority = Literal["low", "medium", "high"]
Status = Literal["todo", "in_progress", "blocked", "review", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    priority: Priority = "medium"
    due_at: date | None = None
    assignee_id: uuid.UUID


class TaskUpdate(BaseModel):
    """Send only what changes: a field left out stays as it is, `due_at: null` clears the date."""

    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    priority: Priority | None = None
    due_at: date | None = None
    assignee_id: uuid.UUID | None = None


class StatusMove(BaseModel):
    to: Status
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    completed_on: date | None = None  # only with `to: done`: the day the work really finished (from the due date, once passed, to today)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_COMMENT_LENGTH)


# ---- responses ----

class PersonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    active: bool


class TransitionResponse(BaseModel):
    to: Status
    kind: str
    label: str
    needs_reason: bool


class TaskActions(BaseModel):
    """What the signed-in person may do with this task right now; the UI shows only these."""

    can_edit: bool
    can_delete: bool
    can_change_assignee: bool
    can_comment: bool
    transitions: list[TransitionResponse]


class LatestReason(BaseModel):
    """Why a task is Blocked, was sent back, or was reopened: the note on its latest status move."""

    kind: Literal["blocked", "sent_back", "reopened"]
    note: str
    at: datetime
    actor_name: str | None


class TaskResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    title: str
    description: str
    status: Status
    priority: Priority
    due_at: date | None
    creator: PersonSummary | None
    assignee: PersonSummary | None
    returned_count: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    overdue: bool
    due_soon: bool
    needs_reassignment: bool
    returned: bool
    latest_reason: LatestReason | None
    actions: TaskActions


class ActivityResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_title: str
    actor: PersonSummary | None
    kind: str
    source: str
    field: str | None
    old_value: str | None
    new_value: str | None
    note: str | None
    created_at: datetime


class TaskDetail(BaseModel):
    task: TaskResponse
    timeline: list[ActivityResponse]


class BoardTeam(BaseModel):
    id: uuid.UUID
    name: str
    manager: PersonSummary | None


class BoardStats(BaseModel):
    todo: int
    in_progress: int
    blocked: int
    overdue: int
    done: int


class ReportCounts(BaseModel):
    """One person's (or the whole team's) numbers. The status counts are the current state; assigned, done and
    returned are limited to the period when there is one."""

    todo: int
    in_progress: int
    blocked: int
    review: int
    overdue: int
    assigned: int  # created in the period
    done: int  # closed in the period
    returned: int  # send-backs on the tasks created in the period
    completion_rate: float | None  # done / assigned
    on_time_rate: float | None  # done on or before the due date, among done tasks that had one
    avg_days_to_close: float | None


class ReportPerson(BaseModel):
    person: PersonSummary
    counts: ReportCounts


class ReportBlock(BaseModel):
    totals: ReportCounts
    people: list[ReportPerson]


class TeamReport(BaseModel):
    all_time: ReportBlock
    period: ReportBlock


class TeamRow(BaseModel):
    team: BoardTeam
    counts: ReportCounts  # the whole team
    people: list[ReportPerson]  # who the team's tasks are assigned to, by name, each with their own numbers


class TeamsBlock(BaseModel):
    totals: ReportCounts  # every task in every team
    teams: list[TeamRow]  # one row per team, by name, including teams with no tasks


class AllTeamsReport(BaseModel):
    all_time: TeamsBlock
    period: TeamsBlock


class Board(BaseModel):
    team: BoardTeam
    read_only: bool  # an admin looking at a team they do not run
    tasks: list[TaskResponse]
    people: list[PersonSummary]  # the team's active people, for the person dropdown
    filter_counts: dict[str, int]
    attention_count: int
    stats: BoardStats
    orphans: list[TaskResponse]  # open tasks that need a new owner, whatever the filters say
