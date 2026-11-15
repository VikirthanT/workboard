"""Suggestion endpoints: the page for a team, the sync, edit / reject / restore, and adding to the board.

A router reads the request, runs one command, then one query to build the reply. The rules (who may do what, what a task
needs) live in `standups/services` and `security/authorization.py`. Every endpoint needs a signed-in person (401
otherwise); errors come back as {"detail": {"code", "message"}}, listed in `standups/README.md`.
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from database.config import get_db
from identity.services.lookup import get_team
from models import Person, TaskSuggestion
from standups import schemas
from standups.services import queries, suggestions as commands, sync
from standups.standup_db.reader import Submission
from security import rate_limit
from security.authentication import get_current_person
from slack import messages
from slack.services import announce

router = APIRouter(tags=["suggestions"])


def _suggestion(s: TaskSuggestion) -> schemas.SuggestionResponse:
    return schemas.SuggestionResponse.model_validate(s)


def _standup(sub: Submission | None) -> schemas.StandupResponse | None:
    if sub is None:
        return None
    sections = bool((sub.this_week or "").strip())
    return schemas.StandupResponse(
        date=sub.standup_date,
        posted_at=sub.posted_at,
        late_reply=sub.is_late_reply,
        last_week=sub.last_week if sections else None,
        this_week=sub.this_week if sections else None,
        blockers=sub.blockers if sections else None,
        message=None if sections else ((sub.combined or "").strip() or sub.raw_content),
    )


def _page(
    db: Session,
    actor: Person,
    team_id: uuid.UUID,
) -> schemas.SuggestionsPageResponse:
    team = get_team(db, team_id)
    page = queries.list_for_team(db, actor, team_id)
    return schemas.SuggestionsPageResponse(
        standup_channel_id=team.standup_channel_id,
        last_synced_at=queries.last_synced(db, team_id),
        standup_problem=page.standup_problem,
        people=[
            schemas.PersonSuggestionsResponse(
                person=schemas.SuggestionPerson(id=e.person.id, name=e.person.name, email=e.person.email, role=e.person.role),
                standup=_standup(e.standup),
                suggestions=[_suggestion(s) for s in e.suggestions],
            )
            for e in page.people
        ],
    )


@router.get("/teams/{team_id}/suggestions", response_model=schemas.SuggestionsPageResponse)
def list_suggestions(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Each person on the team, the standup they last posted (three sections, or one message, or null when they posted
    nothing) and the suggestions from it. Suggestions show for 3 days after they last changed.

    Who: the team's manager, or an admin (read only). Errors: 403 `forbidden`, 404 `team_not_found`.
    """
    return _page(db, actor, team_id)


@router.post("/teams/{team_id}/suggestions/sync", response_model=schemas.SuggestionsPageResponse)
def sync_suggestions(
    team_id: uuid.UUID,
    person_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Read the team's standup channel (this week's standups only: those dated on or after this week's Monday), propose tasks from the team's people's posts, and return the
    page. Posts already read and unchanged are skipped. Runs the language model, so it can take a while.

    `person_id` (optional) syncs only that person, so a manager can go one person at a time.

    shortcut: runs inside the request, and two syncs at once can race on the same post, when one fails on the unique
    rule and the other's work stands; move to a background job if syncs get slow or are triggered automatically.

    Who: the team's own manager, or any admin (403 `forbidden`); an admin's sync only stores suggestions for the manager to
    review, and everything after it (edit, reject, restore, add) stays with the manager. Errors: 404 `person_not_on_team`; 409 `standup_channel_not_set`;
    501 `standups_not_configured` or `llm_not_configured`; 502 `llm_failed` (nothing from the failed post is kept,
    earlier ones are).
    """
    rate_limit.check(("sync", actor.id), rate_limit.SYNC_PER_MINUTE, 60)  # it runs the language model: three a minute
    sync.sync_team(db, actor, team_id, person_id)
    return _page(db, actor, team_id)


@router.post("/teams/{team_id}/suggestions/add", response_model=schemas.SuggestionsPageResponse)
def add_suggestions(
    team_id: uuid.UUID,
    body: schemas.AddSuggestions,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Create a task from each chosen pending suggestion, assigned to the person it is for. All or nothing: if one breaks
    a task rule (for example a due date in the past), none is added and the message names it. When Slack is set up the
    new tasks are then announced in the team's standup channel as one message and one PDF (after this reply).

    A due date is compulsory. A suggestion that has none must be given one in `due_dates` (by suggestion id), and the manager
    may change any date there; the date is kept on the suggestion.

    Who: the team's own manager. Body: {suggestion_ids, due_dates?}. Errors: 403 `forbidden`; 404 `suggestion_not_found`;
    409 `suggestion_not_pending`; 422 `due_date_required` (the message names the suggestion) and `invalid_due_dates` (a date for
    a suggestion not being added); and the task rules' own codes (`due_date_past`, ...), with the title in the message.
    """
    commands.add_to_board(db, actor, team_id, body.suggestion_ids, body.due_dates)
    background.add_task(announce.flush_team, team_id, messages.HEADING_STANDUP)
    return _page(db, actor, team_id)


@router.patch("/suggestions/{suggestion_id}", response_model=schemas.SuggestionResponse)
def edit_suggestion(
    suggestion_id: uuid.UUID,
    body: schemas.SuggestionEdit,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Change a pending suggestion: title, description, priority, person, start or due date. Sending a due date makes it
    the manager's own, no longer the default.

    Who: the team's own manager. Errors: 403 `forbidden`; 404 `suggestion_not_found`; 409 `suggestion_not_pending`;
    422 `invalid_title`, `invalid_description`, `invalid_priority`, `invalid_assignee`.
    """
    commands.edit_suggestion(db, actor, suggestion_id, body.model_dump(exclude_unset=True))
    return _suggestion(queries.get_suggestion(db, actor, suggestion_id))


@router.post("/suggestions/{suggestion_id}/reject", response_model=schemas.SuggestionResponse)
def reject_suggestion(
    suggestion_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Reject a pending suggestion. It stays visible, and restorable, for 3 days.

    Who: the team's own manager. Errors: 403 `forbidden`; 404 `suggestion_not_found`; 409 `suggestion_not_pending`.
    """
    commands.reject_suggestion(db, actor, suggestion_id)
    return _suggestion(queries.get_suggestion(db, actor, suggestion_id))


@router.post("/suggestions/{suggestion_id}/restore", response_model=schemas.SuggestionResponse)
def restore_suggestion(
    suggestion_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Bring back a suggestion rejected in the last 3 days.

    Who: the team's own manager. Errors: 403 `forbidden`; 404 `suggestion_not_found`; 409 `not_restorable`.
    """
    commands.restore_suggestion(db, actor, suggestion_id)
    return _suggestion(queries.get_suggestion(db, actor, suggestion_id))
