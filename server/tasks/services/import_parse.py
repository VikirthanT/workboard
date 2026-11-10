"""Read an uploaded spreadsheet into rows (a query: reads the file and the directory, changes nothing).

Checks only what the sheet itself can get wrong: columns, blanks, lengths, priority, dates, and that each person
exists. The task rules (past due date, start after due, Done, team) are the commands' and run on each row there.
Problems are collected per row and column so the manager can fix the whole sheet in one pass.
"""
import io
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from models import Person, Team
from tasks.services.import_template import COLUMNS, EXAMPLE_PREFIX, MAX_ROWS, PRIORITIES, REQUIRED, TASKS_SHEET, email_from_label
from tasks.states import MAX_DESCRIPTION_LENGTH, MAX_LABEL_LENGTH, MAX_TITLE_LENGTH


_TEXT_DATES = ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d")


@dataclass
class ImportRow:
    number: int  # the row in the sheet, so an error points at what the manager sees
    title: str
    description: str
    priority: str
    assignee_id: uuid.UUID
    support_id: uuid.UUID | None
    project: str | None
    stage: str | None
    start_at: date | None
    due_at: date | None


@dataclass
class RowError:
    row: int
    column: str
    message: str


def parse_upload(db: Session, team: Team, data: bytes) -> tuple[list[ImportRow], list[RowError]]:
    sheet_rows = _read_sheet(data)
    people = _people_by_email(db, sheet_rows)
    rows: list[ImportRow] = []
    errors: list[RowError] = []
    for number, cells in sheet_rows:
        found: list[RowError] = []
        row = _parse_row(number, cells, team, people, found)
        errors.extend(found)
        if not found:
            rows.append(row)
    if not rows and not errors:
        raise AppError("empty_file", "The sheet has no tasks in it.", 422)
    return rows, errors


def only_rows(rows: list[ImportRow], wanted: str) -> list[ImportRow]:
    """The rows the manager ticked, from "2,5" (sheet row numbers). Every number must be one of the sheet's tasks."""
    numbers = {str(r.number) for r in rows}
    picked = {n.strip() for n in wanted.split(",")}
    if not picked <= numbers:  # also catches "", "x" and a row that is not in the sheet
        raise AppError("invalid_rows", "Pick the rows to add from the list.", 422)
    return [r for r in rows if str(r.number) in picked]


def preview(db: Session, rows: list[ImportRow]) -> list[dict]:
    """The rows as the manager will see them before confirming: people by name, dates as ISO strings."""
    ids = {r.assignee_id for r in rows} | {r.support_id for r in rows if r.support_id}
    names = dict(db.execute(select(Person.id, Person.name).where(Person.id.in_(ids))).all())
    return [
        {
            "row": r.number, "title": r.title, "description": r.description, "priority": r.priority,
            "assignee": names[r.assignee_id], "support": names.get(r.support_id) if r.support_id else None,
            "project": r.project, "stage": r.stage,
            "start_at": r.start_at.isoformat() if r.start_at else None, "due_at": r.due_at.isoformat() if r.due_at else None,
        }
        for r in rows
    ]


def _read_sheet(data: bytes) -> list[tuple[int, dict[str, object]]]:
    """Non-blank rows as (sheet row number, {column name: cell}), whatever order the columns are in."""
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError):
        raise AppError("invalid_file", "That is not an .xlsx file. Download the template and fill it in.", 422)
    if TASKS_SHEET not in workbook.sheetnames:
        raise AppError("invalid_file", f"The '{TASKS_SHEET}' sheet is missing. Use the downloaded template.", 422)
    lines = workbook[TASKS_SHEET].iter_rows(min_row=1, max_row=MAX_ROWS + 2, values_only=True)
    header = [str(cell or "").replace("*", "").strip().lower() for cell in next(lines, ())]
    missing = [name for name in COLUMNS if name.lower() not in header]
    if missing:
        raise AppError("invalid_file", f"Missing columns: {', '.join(missing)}. Use the downloaded template.", 422)
    rows = []
    for number, line in enumerate(lines, start=2):
        cells = {name: line[header.index(name.lower())] if header.index(name.lower()) < len(line) else None for name in COLUMNS}
        if _text(cells["Title"]).upper().startswith(EXAMPLE_PREFIX):  # the template's demo row
            continue
        if any(_text(cell) for cell in cells.values()):
            rows.append((number, cells))
    if len(rows) > MAX_ROWS:
        raise AppError("too_many_rows", f"At most {MAX_ROWS} tasks per upload.", 422)
    return rows


def _people_by_email(db: Session, sheet_rows: list[tuple[int, dict[str, object]]]) -> dict[str, Person]:
    emails = {
        email
        for _, cells in sheet_rows
        for column in ("Assignee", "Support")
        if (email := email_from_label(_text(cells[column])))
    }
    return {p.email: p for p in db.scalars(select(Person).where(Person.email.in_(emails)))}


def _parse_row(number: int, cells: dict[str, object], team: Team, people: dict[str, Person], errors: list[RowError]):
    def fail(column: str, message: str) -> None:
        errors.append(RowError(number, column, message))

    title = _text(cells["Title"])
    if not title:
        fail("Title", "Title is required.")
    elif len(title) > MAX_TITLE_LENGTH:
        fail("Title", f"At most {MAX_TITLE_LENGTH} characters.")
    description = _text(cells["Description"])
    if len(description) > MAX_DESCRIPTION_LENGTH:
        fail("Description", f"At most {MAX_DESCRIPTION_LENGTH} characters.")
    priority = _text(cells["Priority"]).lower() or "medium"
    if priority not in PRIORITIES:
        fail("Priority", f"Use one of: {', '.join(PRIORITIES)}.")
    assignee = _person(cells["Assignee"], people, "Assignee", fail, required=True)
    if assignee and (not assignee.active or assignee.team_id != team.id):
        fail("Assignee", "That person is not an active member of your team.")
    support = _person(cells["Support"], people, "Support", fail)
    if support and not support.active:
        fail("Support", "That person is not active.")
    project, stage = (_text(cells[column]) or None for column in ("Project", "Stage"))
    for column, value in (("Project", project), ("Stage", stage)):
        if value and len(value) > MAX_LABEL_LENGTH:
            fail(column, f"At most {MAX_LABEL_LENGTH} characters.")
    start_at = _date(cells["Start date"], "Start date", fail) or date.today()  # left blank: the day of the upload
    due_at = _date(cells["Due date"], "Due date", fail)
    if errors:
        return None
    return ImportRow(number, title, description, priority, assignee.id, support.id if support else None,
                     project, stage, start_at, due_at)


def _person(cell: object, people: dict[str, Person], column: str, fail, required: bool = False) -> Person | None:
    text = _text(cell)
    if not text:
        if required:
            fail(column, f"{column} is required.")
        return None
    person = people.get(email_from_label(text) or "")
    if person is None:
        fail(column, f"No one in the directory matches '{text}'. Pick from the list.")
    return person


def _date(cell: object, column: str, fail) -> date | None:
    if isinstance(cell, datetime):
        return cell.date()
    if isinstance(cell, date):
        return cell
    text = _text(cell)
    if not text:
        return None
    # A cell pasted as text. Day first, never month first: 03/04/2026 is 3 April. Real date cells never get here.
    for pattern in _TEXT_DATES:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    fail(column, "Use a date such as 30-Nov-2026.")
    return None


def _text(cell: object) -> str:
    return "" if cell is None else str(cell).strip()
