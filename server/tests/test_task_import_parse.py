"""Bulk upload, part one: the template download and the sheet parser."""
import io
from datetime import date

import pytest
from openpyxl import Workbook, load_workbook

from core.exceptions import AppError
from models import Team
from tasks.services.import_parse import parse_upload
from tasks.services.import_template import COLUMNS, email_from_label, person_label


def sheet(*rows, headers=COLUMNS) -> bytes:
    """A filled-in Tasks sheet; each row is a dict keyed by column name."""
    book = Workbook()
    book.active.title = "Tasks"
    book.active.append(list(headers))
    for row in rows:
        book.active.append([row.get(name) for name in headers])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def team_of(db, npi) -> Team:
    return db.get(Team, npi["asha"].team_id)


# ---- the template ----

def test_the_template_lists_the_team_and_the_directory_by_username(directory, npi):
    res = directory.call(npi["asha"], "GET", "/tasks/import/template")

    assert res.status_code == 200 and "spreadsheetml" in res.headers["content-type"]
    people = load_workbook(io.BytesIO(res.content))["People"]
    assignees = {r[0] for r in people.iter_rows(min_row=2, values_only=True) if r[0]}
    everyone = {r[1] for r in people.iter_rows(min_row=2, values_only=True) if r[1]}
    assert assignees == {"asha", "ravi"}  # Zoe is on no team
    assert {"asha", "ravi", "zoe", "admin"} <= everyone
    slack_ids = {r[6] for r in people.iter_rows(min_row=2, values_only=True) if r[6]}
    assert npi["ravi"].slack_user_id in slack_ids


def test_the_template_has_a_grey_example_row_and_readable_dates(directory, npi):
    res = directory.call(npi["asha"], "GET", "/tasks/import/template")

    tasks = load_workbook(io.BytesIO(res.content))["Tasks"]
    row = {c.value: tasks.cell(row=2, column=i).value for i, c in enumerate(tasks[1], start=1)}
    assert str(row["Title *"]).startswith("[EXAMPLE]")
    assert row["Assignee *"] in {"asha", "ravi"}  # a real person on the team, so the demo looks right
    assert tasks["I2"].number_format == "dd-mmm-yyyy" and tasks["H9"].number_format == "dd-mmm-yyyy"
    assert tasks["A2"].font.italic


def test_the_downloaded_template_uploads_as_empty_and_skips_its_example(db, directory, npi):
    template = directory.call(npi["asha"], "GET", "/tasks/import/template").content
    team = team_of(db, npi)

    with pytest.raises(AppError) as err:  # nothing but the demo row
        parse_upload(db, team, template)
    assert err.value.code == "empty_file"

    book = load_workbook(io.BytesIO(template))
    book["Tasks"]["A3"], book["Tasks"]["D3"] = "Real task", "ravi"  # not append(): the formatted cells run to row 501
    out = io.BytesIO()
    book.save(out)
    rows, errors = parse_upload(db, team, out.getvalue())
    assert errors == [] and [(r.number, r.title) for r in rows] == [(3, "Real task")]


def test_only_a_manager_can_download_the_template(directory, npi, admin):
    assert directory.call(npi["zoe"], "GET", "/tasks/import/template").status_code == 403
    assert directory.call(admin, "GET", "/tasks/import/template").status_code == 403
    assert directory.call(None, "GET", "/tasks/import/template").status_code == 401


def test_a_label_round_trips_to_the_email(directory):
    ravi = directory.person("Ravi")
    assert email_from_label(person_label(ravi)) == ravi.email
    assert email_from_label("Ravi@AtiMotors.com ") == ravi.email


# ---- the parser ----

def test_a_good_sheet_becomes_rows(db, directory, npi):
    data = sheet({
        "Title": "Wire harness", "Priority": "High", "Assignee": "ravi", "Support": "zoe", "Project": "P1",
        "Stage": "Design", "Start date": date(2030, 1, 1), "Due date": "2030-02-01",
    })

    rows, errors = parse_upload(db, team_of(db, npi), data)

    assert errors == []
    row = rows[0]
    assert (row.number, row.title, row.priority, row.project, row.stage) == (2, "Wire harness", "high", "P1", "Design")
    assert (row.assignee_id, row.support_id) == (npi["ravi"].id, npi["zoe"].id)
    assert (row.start_at, row.due_at) == (date(2030, 1, 1), date(2030, 2, 1))


def test_dates_typed_as_text_are_read_day_first(db, directory, npi):
    rows, errors = parse_upload(db, team_of(db, npi), sheet(
        {"Title": "A", "Assignee": "ravi", "Start date": "03/04/2030", "Due date": "30-Nov-2030"},
        {"Title": "B", "Assignee": "ravi", "Due date": "04/30/2030"},  # month first is not a date here
    ))

    assert [(e.row, e.column) for e in errors] == [(3, "Due date")]
    assert [(r.start_at, r.due_at) for r in rows] == [(date(2030, 4, 3), date(2030, 11, 30))]


def test_blank_rows_are_skipped_and_the_defaults_apply(db, directory, npi):
    rows, errors = parse_upload(db, team_of(db, npi), sheet({}, {"Title": "A", "Assignee": "asha"}, {}))

    assert errors == [] and [(r.number, r.priority, r.description) for r in rows] == [(3, "medium", "")]
    assert (rows[0].start_at, rows[0].due_at) == (date.today(), None)  # a blank start date is the upload day


def test_every_problem_is_reported_with_its_row_and_column(db, directory, npi):
    data = sheet(
        {"Title": "", "Assignee": "ravi"},
        {"Title": "B", "Assignee": "zoe", "Priority": "urgent"},  # Zoe is not on the team
        {"Title": "C", "Assignee": "nobody", "Due date": "next week"},
        {"Title": "D"},
    )

    rows, errors = parse_upload(db, team_of(db, npi), data)

    assert rows == []
    assert [(e.row, e.column) for e in errors] == [
        (2, "Title"), (3, "Priority"), (3, "Assignee"), (4, "Assignee"), (4, "Due date"), (5, "Assignee"),
    ]


# ---- the upload endpoint ----

def upload(directory, who, data):
    return directory.call(who, "POST", "/tasks/import", files={"file": ("tasks.xlsx", data, "application/octet-stream")})


def test_an_upload_creates_every_task_with_its_timeline(directory, npi):
    data = sheet(
        {"Title": "A", "Assignee": "ravi", "Support": "zoe", "Project": "P1", "Stage": "Design", "Priority": "high"},
        {"Title": "B", "Assignee": "asha"},
    )

    res = upload(directory, npi["asha"], data)

    assert (res.status_code, res.json()) == (201, {"created": 2})
    tasks = sorted(directory.call(npi["asha"], "GET", "/board").json()["tasks"], key=lambda t: t["title"])
    assert [(t["title"], t["priority"], t["status"]) for t in tasks] == [("A", "high", "todo"), ("B", "medium", "todo")]
    assert (tasks[0]["support"]["name"], tasks[0]["project"], tasks[0]["stage"]) == ("Zoe", "P1", "Design")
    detail = directory.call(npi["asha"], "GET", f"/tasks/{tasks[0]['id']}").json()
    assert [a["kind"] for a in detail["timeline"]] == ["created"]


def test_a_preview_lists_the_rows_and_saves_nothing(directory, npi):
    data = sheet({"Title": "A", "Assignee": "ravi", "Support": "zoe", "Project": "P1", "Priority": "high"})

    res = directory.call(npi["asha"], "POST", "/tasks/import?preview=true", files={"file": ("tasks.xlsx", data, "application/octet-stream")})

    assert res.status_code == 200
    [row] = res.json()["tasks"]
    assert (row["row"], row["title"], row["assignee"], row["support"], row["project"], row["priority"]) == (2, "A", "Ravi", "Zoe", "P1", "high")
    assert directory.call(npi["asha"], "GET", "/board").json()["tasks"] == []


def test_only_the_ticked_rows_are_added(directory, npi):
    data = sheet({"Title": "A", "Assignee": "ravi"}, {"Title": "B", "Assignee": "ravi"}, {"Title": "C", "Assignee": "ravi"})

    res = directory.call(npi["asha"], "POST", "/tasks/import?rows=2,4", files={"file": ("tasks.xlsx", data, "application/octet-stream")})

    assert (res.status_code, res.json()) == (201, {"created": 2})
    assert sorted(t["title"] for t in directory.call(npi["asha"], "GET", "/board").json()["tasks"]) == ["A", "C"]


@pytest.mark.parametrize("rows", ["9", "2,x", "2,,3", ","])
def test_a_row_that_is_not_in_the_sheet_is_refused(directory, npi, rows):
    data = sheet({"Title": "A", "Assignee": "ravi"}, {"Title": "B", "Assignee": "ravi"})

    res = directory.call(npi["asha"], "POST", f"/tasks/import?rows={rows}", files={"file": ("tasks.xlsx", data, "application/octet-stream")})

    assert (res.status_code, res.json()["detail"]["code"]) == (422, "invalid_rows")
    assert directory.call(npi["asha"], "GET", "/board").json()["tasks"] == []


def test_a_preview_reports_task_rule_errors_too(directory, npi):
    data = sheet({"Title": "Late", "Assignee": "ravi", "Due date": date(2020, 1, 1)})

    res = directory.call(npi["asha"], "POST", "/tasks/import?preview=true", files={"file": ("tasks.xlsx", data, "application/octet-stream")})

    assert res.status_code == 422 and [e["row"] for e in res.json()["detail"]["errors"]] == [2]


def test_one_bad_row_saves_nothing(directory, npi):
    past = date(2020, 1, 1)  # passes the sheet checks, then breaks the "due date not in the past" rule
    data = sheet({"Title": "Good", "Assignee": "ravi"}, {"Title": "Late", "Assignee": "ravi", "Due date": past})

    res = upload(directory, npi["asha"], data)

    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "import_invalid" and [e["row"] for e in detail["errors"]] == [3]
    assert directory.call(npi["asha"], "GET", "/board").json()["tasks"] == []


def test_sheet_errors_come_back_per_row_and_save_nothing(directory, npi):
    res = upload(directory, npi["asha"], sheet({"Title": "A", "Assignee": "zoe"}, {"Title": "", "Assignee": "ravi"}))

    assert res.status_code == 422
    assert [(e["row"], e["column"]) for e in res.json()["detail"]["errors"]] == [(2, "Assignee"), (3, "Title")]
    assert directory.call(npi["asha"], "GET", "/board").json()["tasks"] == []


def test_upload_is_for_managers_and_refuses_bad_files(directory, npi, admin):
    good = sheet({"Title": "A", "Assignee": "ravi"})
    assert upload(directory, npi["zoe"], good).status_code == 403
    assert upload(directory, admin, good).status_code == 403
    assert upload(directory, None, good).status_code == 401
    assert upload(directory, npi["asha"], b"junk").json()["detail"]["code"] == "invalid_file"
    assert upload(directory, npi["asha"], b"x" * (2 * 1024 * 1024 + 1)).json()["detail"]["code"] == "file_too_large"


def test_a_file_that_is_not_the_template_is_refused(db, directory, npi):
    team = team_of(db, npi)
    for data in (b"not a spreadsheet", sheet(headers=("Title", "Assignee")), sheet()):
        with pytest.raises(AppError) as err:
            parse_upload(db, team, data)
        assert err.value.status_code == 422
