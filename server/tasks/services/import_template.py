"""The bulk-upload spreadsheet: one .xlsx the manager downloads, fills in and uploads (a query: reads, changes nothing).

The people dropdowns hold the email's username, the part before the company domain ("asha.k" for
asha.k@atimotors.com). The upload adds the domain back, so a renamed person still matches. The People sheet also
lists each person's name and Slack ID for lookup. The lists are written from the directory each time the template
is downloaded, so a later Slack sync shows up on the next download.
"""
import io
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from models import Person, Team
from tasks.services.lookup import own_team
from tasks.states import MAX_LABEL_LENGTH, MAX_TITLE_LENGTH

TASKS_SHEET = "Tasks"
PEOPLE_SHEET = "People"
PRIORITIES = ("high", "medium", "low")
# One entry per column of the Tasks sheet, in order. The upload reads the header text, so keep these in step with it.
COLUMNS = ("Title", "Description", "Priority", "Assignee", "Support", "Project", "Stage", "Start date", "Due date")
REQUIRED = ("Title", "Assignee")
MAX_ROWS = 500  # rows the dropdowns and date formats cover, and the most one upload takes
EXAMPLE_PREFIX = "[EXAMPLE]"  # the template's demo row starts with this; the upload skips any row that does
DATE_FORMAT = "dd-mmm-yyyy"  # a month name cannot be misread as day/month the way 03/04 can

def person_label(person: Person) -> str:
    """The username for company emails; the whole address for any other domain, so it stays unique."""
    username, _, domain = person.email.partition("@")
    return username if domain == settings.allowed_email_domain else person.email


def email_from_label(text: str) -> str | None:
    """The email behind a dropdown value; a full address typed by hand is accepted too."""
    text = text.strip().lower()
    if not text or " " in text:
        return None
    return text if "@" in text else f"{text}@{settings.allowed_email_domain}"


def template_for(db: Session, actor: Person) -> bytes:
    """The template for the actor's own team; anyone who could not create a task there is refused."""
    return build_template(db, own_team(db, actor))


def build_template(db: Session, team: Team) -> bytes:
    people = db.scalars(select(Person).where(Person.active).order_by(Person.name)).all()
    members = [p for p in people if p.team_id == team.id]

    workbook = Workbook()
    tasks = workbook.active
    tasks.title = TASKS_SHEET
    tasks.append([f"{name} *" if name in REQUIRED else name for name in COLUMNS])
    tasks.freeze_panes = "A2"
    for index, name in enumerate(COLUMNS, start=1):
        tasks.column_dimensions[get_column_letter(index)].width = 40 if name in ("Title", "Description") else 28

    lists = workbook.create_sheet(PEOPLE_SHEET)
    lists.append(["Team members (Assignee)", "Everyone (Support)", "Priority", None, "Username", "Name", "Slack ID"])
    for row in range(max(len(members), len(people), len(PRIORITIES))):
        person = people[row] if row < len(people) else None
        lists.append([
            person_label(members[row]) if row < len(members) else None,
            person_label(person) if person else None,
            PRIORITIES[row] if row < len(PRIORITIES) else None,
            None,
            person_label(person) if person else None,
            person.name if person else None,
            person.slack_user_id if person else None,
        ])
    for letter in "ABCEFG":
        lists.column_dimensions[letter].width = 30

    _dropdown(tasks, "Priority", f"={PEOPLE_SHEET}!$C$2:$C${1 + len(PRIORITIES)}")
    _dropdown(tasks, "Assignee", f"={PEOPLE_SHEET}!$A$2:$A${1 + max(len(members), 1)}")
    _dropdown(tasks, "Support", f"={PEOPLE_SHEET}!$B$2:$B${1 + max(len(people), 1)}")
    for name, earliest in (("Start date", "DATE(2000,1,1)"), ("Due date", "TODAY()")):
        letter = get_column_letter(COLUMNS.index(name) + 1)
        for row in range(2, MAX_ROWS + 2):
            tasks[f"{letter}{row}"].number_format = DATE_FORMAT
        rule = DataValidation(type="date", operator="greaterThanOrEqual", formula1=earliest, allow_blank=True)
        rule.error = f"Enter a date such as 30-Nov-2026{', today or later' if name == 'Due date' else ''}."
        rule.showErrorMessage = True
        rule.add(f"{letter}2:{letter}{MAX_ROWS + 1}")
        tasks.add_data_validation(rule)
    _example_row(tasks, members, people)
    _length_limit(tasks, "Title", MAX_TITLE_LENGTH)
    _length_limit(tasks, "Project", MAX_LABEL_LENGTH)
    _length_limit(tasks, "Stage", MAX_LABEL_LENGTH)

    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def _example_row(sheet, members: list[Person], people: list[Person]) -> None:
    """Row 2 shows how a row looks. It is grey, and the upload skips it, so leaving it in does no harm."""
    example = {
        "Title": f"{EXAMPLE_PREFIX} Order the wiring harness",
        "Description": "Delete this row or leave it: it is ignored.",
        "Priority": "medium",
        "Assignee": person_label(members[0]) if members else None,
        "Support": person_label(people[-1]) if people else None,
        "Project": "Project name",
        "Stage": "Design",
        "Start date": date.today(),
        "Due date": date.today() + timedelta(days=7),
    }
    for index, name in enumerate(COLUMNS, start=1):
        cell = sheet.cell(row=2, column=index, value=example[name])
        cell.font = Font(italic=True, color="808080")


def _dropdown(sheet, column: str, source: str) -> None:
    letter = get_column_letter(COLUMNS.index(column) + 1)
    rule = DataValidation(type="list", formula1=source, allow_blank=True, showErrorMessage=True)
    rule.error = f"Pick a {column.lower()} from the list."
    rule.add(f"{letter}2:{letter}{MAX_ROWS + 1}")
    sheet.add_data_validation(rule)


def _length_limit(sheet, column: str, limit: int) -> None:
    letter = get_column_letter(COLUMNS.index(column) + 1)
    rule = DataValidation(type="textLength", operator="lessThanOrEqual", formula1=str(limit), allow_blank=True)
    rule.error = f"At most {limit} characters."
    rule.showErrorMessage = True
    rule.add(f"{letter}2:{letter}{MAX_ROWS + 1}")
    sheet.add_data_validation(rule)
