"""The team report: per person and in total, for all time and for a chosen period. A query: it changes nothing.
Done tasks are never hidden here. Mirrors client/src/app/domain/report.ts.

shortcut: a timestamp's calendar day is the server's own time zone (the same one `today` uses); fine for one office.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from models import Person, Task, Team
from tasks import rules, schemas

Window = tuple[date, date]


def _day(moment: datetime) -> date:
    return moment.astimezone().date()


def _in(moment: datetime | None, window: Window | None) -> bool:
    return moment is not None and (window is None or window[0] <= _day(moment) <= window[1])


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def report_counts(tasks: list[Task], window: Window | None, today: date) -> schemas.ReportCounts:
    """shortcut: completion_rate can pass 100% in a period (work created earlier, closed now), fine for a report."""
    assigned = [t for t in tasks if _in(t.created_at, window)]
    done = [t for t in tasks if t.status == "done" and _in(t.closed_at, window)]
    with_due = [t for t in done if t.due_at is not None]
    days_to_close = [(_day(t.closed_at) - _day(t.created_at)).days for t in done]
    return schemas.ReportCounts(
        todo=sum(t.status == "todo" for t in tasks),
        in_progress=sum(t.status == "in_progress" for t in tasks),
        blocked=sum(t.status == "blocked" for t in tasks),
        review=sum(t.status == "review" for t in tasks),
        overdue=sum(rules.is_overdue(t, today) for t in tasks),
        assigned=len(assigned),
        done=len(done),
        returned=sum(t.returned_count for t in assigned),
        completion_rate=_ratio(len(done), len(assigned)),
        on_time_rate=_ratio(sum(_day(t.closed_at) <= t.due_at for t in with_due), len(with_due)),
        avg_days_to_close=sum(days_to_close) / len(days_to_close) if days_to_close else None,
    )


def get_all_teams_report(db: Session, date_from: date, date_to: date, *, today: date | None = None) -> schemas.AllTeamsReport:
    """Every team side by side, and the overall total. The caller must be an admin (the router checks).
    A team with no tasks still gets a row of zeros, so a missing team is never mistaken for a quiet one."""
    if date_from > date_to:
        raise AppError("invalid_range", "The From date must not be after the To date.", 422)
    today = today or date.today()
    all_teams = list(db.scalars(select(Team).order_by(func.lower(Team.name), Team.id)))
    tasks = list(db.scalars(select(Task)))
    by_team: dict[uuid.UUID, list[Task]] = {team.id: [] for team in all_teams}
    for task in tasks:
        by_team[task.team_id].append(task)
    owners = _owners(db, tasks)

    def block(window: Window | None) -> schemas.TeamsBlock:
        rows = [
            schemas.TeamRow(
                team=schemas.BoardTeam(
                    id=team.id, name=team.name,
                    manager=schemas.PersonSummary.model_validate(team.manager) if team.manager else None,
                ),
                counts=report_counts(by_team[team.id], window, today),
                people=_person_rows(by_team[team.id], owners, window, today),
            )
            for team in all_teams
        ]
        return schemas.TeamsBlock(totals=report_counts(tasks, window, today), teams=rows)

    return schemas.AllTeamsReport(all_time=block(None), period=block((date_from, date_to)))


def get_team_report(
    db: Session,
    team: Team,
    date_from: date,
    date_to: date,
    *,
    person_id: uuid.UUID | None = None,
    today: date | None = None,
) -> schemas.TeamReport:
    """`team` comes from resolve_board_team, which has already checked the actor may read it."""
    if date_from > date_to:
        raise AppError("invalid_range", "The From date must not be after the To date.", 422)
    today = today or date.today()
    query = select(Task).where(Task.team_id == team.id)
    if person_id is not None:
        query = query.where(Task.assignee_id == person_id)
    tasks = list(db.scalars(query))
    owners = _owners(db, tasks)

    def block(window: Window | None) -> schemas.ReportBlock:
        return schemas.ReportBlock(totals=report_counts(tasks, window, today), people=_person_rows(tasks, owners, window, today))

    return schemas.TeamReport(all_time=block(None), period=block((date_from, date_to)))


def _owners(db: Session, tasks: list[Task]) -> dict[uuid.UUID, Person]:
    """The people the tasks are assigned to, by id (inactive people included: they still had the work)."""
    ids = {t.assignee_id for t in tasks if t.assignee_id}
    return {p.id: p for p in db.scalars(select(Person).where(Person.id.in_(ids)))}


def _person_rows(tasks: list[Task], owners: dict[uuid.UUID, Person], window: Window | None, today: date) -> list[schemas.ReportPerson]:
    """One row per person who has any of these tasks, by name. A task with no owner counts in the totals, not here."""
    mine = {t.assignee_id for t in tasks if t.assignee_id}
    return [
        schemas.ReportPerson(
            person=schemas.PersonSummary.model_validate(owner),
            counts=report_counts([t for t in tasks if t.assignee_id == owner.id], window, today),
        )
        for owner in sorted((owners[i] for i in mine), key=lambda p: p.name)
    ]
