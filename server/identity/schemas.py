import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from identity.states import MAX_REASON_LENGTH

Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    """One page of a longer list. `total` counts every match, not just this page."""

    items: list[Item]
    total: int
    limit: int
    offset: int


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    slack_user_id: str
    role: str
    is_admin: bool
    active: bool
    team_id: uuid.UUID | None
    team_name: str | None
    # Tasks assigned to them that are not Done. Only the team members list fills it in; everywhere else it is null.
    open_task_count: int | None = None


class DevAccount(BaseModel):
    """One line of the dev sign-in list. `can_sign_in` is false for people the server will refuse."""

    email: str
    name: str
    can_sign_in: bool


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    active: bool
    manager: PersonResponse | None
    member_count: int


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    initial_manager_person_id: uuid.UUID
    reason: str = Field(max_length=MAX_REASON_LENGTH)


class TeamDelete(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=100)
    reason: str = Field(max_length=MAX_REASON_LENGTH)


class ManagerChange(BaseModel):
    person_id: uuid.UUID
    reason: str = Field(max_length=MAX_REASON_LENGTH)


class MemberAdd(BaseModel):
    person_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)


class MemberRemove(BaseModel):
    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)


class AdminToggle(BaseModel):
    is_admin: bool
    reason: str = Field(max_length=MAX_REASON_LENGTH)


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    team_id: uuid.UUID | None
    person_id: uuid.UUID | None
    reason: str | None
    details: dict | None
    created_at: datetime
    # Looked up when the page is built, so the screen can say who did what to whom. None when that person or team no
    # longer exists and the entry does not carry its name (the log has no foreign keys, so it outlives both).
    actor_name: str | None = None
    person_name: str | None = None
    team_name: str | None = None
