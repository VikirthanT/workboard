"""Bulk upload: download the spreadsheet template, upload it filled in.

Registered before `tasks.py` so `/tasks/import/...` is never read as `/tasks/{id}`.
"""
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile  # what request.form() returns (not fastapi's subclass)

from core.exceptions import AppError
from database.config import get_db
from models import Person
from security import rate_limit
from security.authentication import get_current_person
from tasks.services import commands, import_parse, import_template
from tasks.services.lookup import own_team

router = APIRouter(prefix="/tasks/import", tags=["tasks"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_FILE_BYTES = 2 * 1024 * 1024  # 500 rows of text is well under this; it keeps a huge file out of memory
MULTIPART_OVERHEAD_BYTES = 64 * 1024  # boundaries and headers around the file in the request body


@router.get("/template")
def download_template(db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """The .xlsx to fill in, with dropdowns of your team and the directory, built fresh on every download.

    Who: the manager of a team (403 `forbidden` for anyone else).
    """
    return Response(
        import_template.template_for(db, actor),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="workboard-tasks-template.xlsx"'},
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_tasks(
    request: Request,
    preview: bool = False,
    rows_: str = Query(default="", alias="rows", description="Comma-separated sheet row numbers to add; all when left out"),
    db: Session = Depends(get_db),
    actor: Person = Depends(get_current_person),
):
    """Create every task in the filled-in template on the caller's own team, all or nothing.

    Who: the manager of a team (403 `forbidden` for anyone else). Body: multipart form with the `.xlsx` as `file`.
    Returns 201 `{"created": n}`. With `?preview=true` every check runs but nothing is saved: 200 `{"tasks": [...]}`,
    the rows that would be created, so the manager can look before confirming. `?rows=2,5` adds only those sheet rows
    (the ones ticked in the preview); the rest are left out, and a number that is not a task row is 422 `invalid_rows`.
    If anything is wrong nothing is saved: 422 `import_invalid` with
    `errors: [{row, column, message}]`, one per problem, so the whole sheet can be fixed in one pass.
    Other 422 codes: `invalid_file`, `empty_file`, `too_many_rows`, `file_too_large`.

    The body is read by hand, after the caller is known: a `File(...)` parameter makes FastAPI parse the multipart
    body before it checks who is calling, so an anonymous request would reach the parser.
    """
    team = own_team(db, actor)  # refuse before reading the file
    rate_limit.check(("import", actor.id), rate_limit.IMPORT_PER_MINUTE, 60)  # the costly call: a spreadsheet is parsed
    if int(request.headers.get("content-length") or 0) > MAX_FILE_BYTES + MULTIPART_OVERHEAD_BYTES:
        raise AppError("file_too_large", "The file is larger than 2 MB.", 422)
    form = await request.form(max_files=1, max_fields=1)  # a malformed body is a 400 from here, for a signed-in manager only
    upload = form.get("file")
    if not isinstance(upload, StarletteUploadFile):
        raise AppError("invalid_file", "Attach the template as the form field 'file'.", 422)
    data = await upload.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise AppError("file_too_large", "The file is larger than 2 MB.", 422)
    rows, errors = import_parse.parse_upload(db, team, data)
    if rows_ and not errors:
        rows = import_parse.only_rows(rows, rows_)
    if not errors:
        try:
            commands.import_tasks(db, actor, rows, dry_run=preview)
        except commands.ImportRejected as rejected:
            errors = rejected.errors
    if errors:
        return JSONResponse(
            status_code=422,
            content={"detail": {
                "code": "import_invalid",
                "message": "Nothing was uploaded. Fix the rows below and upload again.",
                "errors": [{"row": e.row, "column": e.column, "message": e.message} for e in errors],
            }},
        )
    if preview:
        return JSONResponse(status_code=200, content={"tasks": import_parse.preview(db, rows)})
    return {"created": len(rows)}
