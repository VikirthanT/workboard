"""Reports: task numbers per person and per team. Queries only: they read and change nothing.

Both reports return two blocks, `all_time` (every task ever) and `period` (the dates asked for). Open work
(To Do, In Progress, Blocked, In Review, Overdue) is always the current state; Assigned, Done and Returned are
limited to the period. The numbers are worked out in `tasks/services/report.py`.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.config import get_db
from models import Person
from security import authorization
from security.authentication import get_current_person
from tasks import schemas
from tasks.services import queries, report

router = APIRouter(tags=["reports"])


@router.get("/reports/all-teams", response_model=schemas.AllTeamsReport)
def all_teams_report(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Every team in one report: a row per team (with the people under it) and the total over all teams.

    Who: admins only (403 `forbidden`).
    Query: `from` and `to`, both dates, `from` not after `to` (422 `invalid_range`).
    A team with no tasks still gets a row of zeros, and a person appears under a team only if they have tasks on it.
    """
    authorization.require_admin(actor)
    return report.get_all_teams_report(db, date_from, date_to)


@router.get("/reports/team", response_model=schemas.TeamReport)
def team_report(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    team: uuid.UUID | None = None,
    person: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """One team's report: a row per person and the team total.

    Who: a manager gets their own team; an admin may ask for any team with `team` (403 `forbidden` for anyone
    else, 400 `choose_team` for an admin who runs no team and names none).
    Query: `from` and `to` (dates, `from` not after `to`: 422 `invalid_range`); `person` limits the report to one
    person's tasks.
    People who have left the directory still appear for the work they had.
    """
    chosen = queries.resolve_board_team(db, actor, team)
    return report.get_team_report(db, chosen, date_from, date_to, person_id=person)
