"""The team board: every card on a team, ready to draw. A query only: it reads and changes nothing.

The reply already contains what the screen needs: the cards (each with the `actions` the caller may take), the
people for the person dropdown, the counts for the filters and the "Needs attention" tick, the numbers for the
five column totals, and the open tasks that need a new owner. The filtering is done here, so the screen does not
have to repeat any rule.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.config import get_db
from models import Person
from security.authentication import get_current_person
from tasks import schemas
from tasks.services import queries

router = APIRouter(tags=["board"])


@router.get("/board", response_model=schemas.Board)
def board(
    team: uuid.UUID | None = None,
    person: uuid.UUID | None = None,
    filter_: str = Query(default="", alias="filter", description="Comma-separated: needs_review, overdue, blocked, due_week"),
    attention: bool = False,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """One team's board.

    Who: a manager sees their own team (and is refused another: 403 `forbidden`). An admin may read any team,
    read-only: the reply says `read_only: true` and every card's `actions` is empty. An admin who runs no team
    must pass `team`, else 400 `choose_team`.
    Query:
      team       which team (admins only; a manager's own team is the default)
      person     keep only this person's cards
      filter     comma list of needs_review, overdue, blocked, due_week; a card must match all of them
                 (an unknown name is 422 `unknown_filter`)
      attention  true keeps only what needs the manager: overdue, blocked, in Review, or without an owner
    Done cards never leave the board: the Done column lists the most recently closed first.
    `filter_counts` says how many cards each filter would show right now, so the menu can show it before you pick.
    """
    chosen = queries.resolve_board_team(db, actor, team)
    return queries.get_board(
        db, actor, chosen, person_id=person, filters=[f for f in filter_.split(",") if f], attention=attention
    )
